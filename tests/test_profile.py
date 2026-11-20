from pathlib import Path

import pytest
from pydantic import ValidationError

from gmaj.profile import Text, load_profile, load_search, profile_to_text, save_profile

EX = Path(__file__).parent.parent / "examples"


def test_examples_load():
    p = load_profile(EX / "profile.example.yaml")
    s = load_search(EX / "search.example.yaml")
    assert p.canonical_lang in ("pt", "en") and len(s.tracks) == 2


def test_text_requires_one_language():
    with pytest.raises(ValidationError):
        Text()


def test_text_get_falls_back():
    assert Text(pt="olá").get("en") == "olá"


def test_duplicate_ids_rejected():
    p = load_profile(EX / "profile.example.yaml")
    p.experiences[1].id = p.experiences[0].id
    with pytest.raises(ValidationError):
        type(p).model_validate(p.model_dump())


def test_unreviewed_lists_auto_paths():
    p = load_profile(EX / "profile.example.yaml")
    assert "experiences[0].bullets[1].text" in p.unreviewed()
    assert "experiences[1].title" in p.unreviewed()


def test_resolved_tracks_inherit_globals():
    s = load_search(EX / "search.example.yaml")
    s.exclude = ["estágio"]
    s.tracks[0].remote = None
    t = s.resolved_tracks()[0]
    assert "estágio" in t.exclude and t.remote == s.remote
    assert s.resolved_tracks()[1].remote == ["remote", "hybrid"]


def test_search_rejects_empty_tracks():
    with pytest.raises(ValidationError):
        type(load_search(EX / "search.example.yaml")).model_validate({"tracks": []})


def test_roundtrip_keeps_accents(tmp_path):
    p = load_profile(EX / "profile.example.yaml")
    save_profile(p, tmp_path / "p.yaml")
    assert load_profile(tmp_path / "p.yaml") == p
    assert "\\u" not in (tmp_path / "p.yaml").read_text(encoding="utf-8")


def test_profile_to_text_has_ids_and_language():
    p = load_profile(EX / "profile.example.yaml")
    txt = profile_to_text(p, "en")
    assert f"[{p.experiences[0].bullets[0].id}]" in txt
    assert p.summary.get("en") in txt
    assert p.summary.get("pt") not in txt


def test_project_name_is_bilingual(example_profile):
    from gmaj.profile import Project
    pr = Project(id="prj-1", name={"pt": "Videomonitoramento", "en": "Video monitoring"}, description={"pt": "x"})
    p = example_profile.model_copy(update={"projects": [pr]})
    assert "Video monitoring" in profile_to_text(p, "en")

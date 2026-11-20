import pytest

from conftest import make_pdf
from gmaj.cli import main
from gmaj.llm import LLMError
from gmaj.onboarding import build_profile, extract_pdf_text, suggest_search
from gmaj.profile import load_profile, load_search


def test_extract_pdf_text(tmp_path):
    p = tmp_path / "cv.pdf"
    p.write_bytes(make_pdf("Ana Exemplo Engenheira Ambiental"))
    assert "Ana Exemplo" in extract_pdf_text(p)


def test_extract_pdf_text_empty_raises(tmp_path):
    p = tmp_path / "cv.pdf"
    p.write_bytes(make_pdf(""))
    with pytest.raises(ValueError, match="no text"):
        extract_pdf_text(p)


def test_build_profile_retries_once_then_succeeds(fake_llm_factory, example_profile_json):
    llm = fake_llm_factory(['{"name": "x"}', example_profile_json])
    p = build_profile("cv text", llm)
    assert p.name == "Ana Exemplo" and len(llm.prompts) == 2
    assert "cv text" in llm.prompts[0] and "validation" in llm.prompts[1].lower()


def test_build_profile_fails_after_two_bad_answers(fake_llm_factory):
    with pytest.raises(LLMError):
        build_profile("cv", fake_llm_factory(["{}", "not json"]))


def test_suggest_search_returns_tracks(fake_llm_factory, example_profile, example_search_json):
    llm = fake_llm_factory([example_search_json])
    s = suggest_search(example_profile, llm)
    assert 1 <= len(s.tracks) <= 4
    assert "gupy" in llm.prompts[0] and "[exp-1]" in llm.prompts[0]


def _patch_llm(monkeypatch, llm):
    monkeypatch.setattr("gmaj.onboarding.get_llm", lambda *a: llm)


def test_cli_init_writes_files(data_dir, tmp_path, monkeypatch, fake_llm_factory, example_profile_json, example_search_json, capsys):
    cv = tmp_path / "cv.pdf"
    cv.write_bytes(make_pdf("Ana"))
    _patch_llm(monkeypatch, fake_llm_factory([example_profile_json, example_search_json]))
    assert main(["init", "--cv", str(cv)]) == 0
    assert load_profile(data_dir / "profile.yaml").name == "Ana Exemplo"
    assert len(load_search(data_dir / "search.yaml").tracks) == 2
    assert "2" in capsys.readouterr().out  # unreviewed translations count


def test_cli_init_refuses_overwrite(data_dir, tmp_path, monkeypatch, fake_llm_factory):
    (data_dir / "profile.yaml").write_text("x")
    cv = tmp_path / "cv.pdf"
    cv.write_bytes(make_pdf("Ana"))
    llm = fake_llm_factory([])
    _patch_llm(monkeypatch, llm)
    assert main(["init", "--cv", str(cv)]) == 1
    assert llm.prompts == [] and (data_dir / "profile.yaml").read_text() == "x"


def test_cli_init_reports_errors_without_traceback(data_dir, tmp_path, capsys):
    assert main(["init", "--cv", str(tmp_path / "missing.pdf")]) == 1
    assert "missing.pdf" in capsys.readouterr().out


def test_build_profile_backend_error_is_not_retried():
    class Down:
        calls = 0

        def complete(self, prompt, json_schema=None):
            Down.calls += 1
            raise LLMError("claude CLI error: Not logged in")

    with pytest.raises(LLMError, match="Not logged in"):
        build_profile("cv", Down())
    assert Down.calls == 1

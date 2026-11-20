from conftest import make_track
from gmaj.jobs import Job
from gmaj.triage import best_track, detect_lang, keyword_score, passes_filters, score_fit


def test_detect_lang():
    assert detect_lang("Buscamos geólogo para atuar com estabilidade de taludes e mapeamento de risco") == "pt"
    assert detect_lang("We are looking for a GIS analyst to support disaster risk teams") == "en"
    assert detect_lang("QGIS ArcGIS Python") == "en"


def test_keyword_score_accent_insensitive_and_title_double():
    t = make_track(keywords={"geotecnia": 2.0, "taludes": 1.0})
    j = Job("x", "1", "u", "Analista de Geotecnia", "Acme", description="estabilidade de TALUDES")
    assert keyword_score(j, t) == 2.0 * 2 + 1.0


def test_keyword_score_accented_keyword_matches_plain_text():
    t = make_track(keywords={"geólogo": 1.0})
    assert keyword_score(Job("x", "1", "u", "Geologo Pleno", "A"), t) == 2.0


def test_keyword_word_boundary():
    t = make_track(keywords={"gis": 1.0})
    assert keyword_score(Job("x", "1", "u", "Logistics Analyst", "A"), t) == 0


def test_exclude_on_title_only():
    t = make_track(keywords={"gis": 1.0}, exclude=["estágio"])
    assert not passes_filters(Job("x", "1", "u", "Estágio em GIS", "A"), t)
    assert passes_filters(Job("x", "1", "u", "GIS Analyst", "A", description="não é estágio"), t)


def test_location_filter():
    t = make_track(locations=["sao paulo", "campinas"])
    assert passes_filters(Job("x", "1", "u", "GIS", "A", location="São Paulo, SP"), t)
    assert not passes_filters(Job("x", "1", "u", "GIS", "A", location="Recife, PE"), t)
    assert passes_filters(Job("x", "1", "u", "GIS", "A", location="Recife, PE", remote="remote"), t)
    assert passes_filters(Job("x", "1", "u", "GIS", "A", location=""), t)


def test_remote_filter():
    t = make_track(remote=["remote"])
    assert not passes_filters(Job("x", "1", "u", "GIS", "A", remote="onsite"), t)
    assert passes_filters(Job("x", "1", "u", "GIS", "A", remote=None), t)


def test_best_track_picks_highest_and_respects_min_score():
    geo = make_track(id="geo", keywords={"geotecnia": 3.0})
    gis = make_track(id="gis", keywords={"gis": 1.0}, min_score=3.0)
    assert best_track(Job("x", "1", "u", "Geotecnia e GIS", "A"), [geo, gis])[0].id == "geo"
    assert best_track(Job("x", "1", "u", "GIS", "A"), [gis]) is None


def test_score_fit_parses_and_clamps(fake_llm_factory, example_profile):
    llm = fake_llm_factory(['```json\n{"score": 140, "summary": "ok", "strengths": ["a"], "gaps": []}\n```'])
    out = score_fit(Job("x", "1", "u", "GIS", "A", description="d"), make_track(name="GIS"), example_profile, "en", llm)
    assert out == {"score": 100, "summary": "ok", "strengths": ["a"], "gaps": []}
    assert example_profile.summary.get("en") in llm.prompts[0] and "GIS" in llm.prompts[0]


def test_score_fit_returns_none_on_bad_json(fake_llm_factory, example_profile):
    assert score_fit(Job("x", "1", "u", "GIS", "A"), make_track(), example_profile, "en", fake_llm_factory(["not json"])) is None


def test_score_fit_returns_none_on_missing_score(fake_llm_factory, example_profile):
    llm = fake_llm_factory(['{"summary": "ok"}'])
    assert score_fit(Job("x", "1", "u", "GIS", "A"), make_track(), example_profile, "en", llm) is None


def test_score_fit_propagates_backend_errors(example_profile):
    import pytest
    from gmaj.llm import LLMError

    class Down:
        def complete(self, prompt, json_schema=None):
            raise LLMError("offline")
    with pytest.raises(LLMError):
        score_fit(Job("x", "1", "u", "GIS", "A"), make_track(), example_profile, "en", Down())

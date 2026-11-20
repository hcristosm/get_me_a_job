import shutil

import pytest
from fastapi.testclient import TestClient

from conftest import EX
from gmaj.db import connect, set_fit, set_triage, upsert_job
from gmaj.jobs import Job
from gmaj.llm import LLMError
from gmaj.web.app import create_app


@pytest.fixture
def seeded(data_dir):
    shutil.copy(EX / "profile.example.yaml", data_dir / "profile.yaml")
    shutil.copy(EX / "search.example.yaml", data_dir / "search.yaml")
    conn = connect(data_dir / "jobs.sqlite")
    a = upsert_job(conn, Job("greenhouse", "1", "https://x/1", "GIS Analyst", "Acme", "Remote", "QGIS daily"))
    b = upsert_job(conn, Job("gupy", "2", "https://x/2", "Analista Ambiental", "Beta", "Campinas", "licenciamento"))
    set_triage(conn, a, track_id="gis-data", keyword_score=6, lang="en", status="new")
    set_triage(conn, b, track_id="env-consulting", keyword_score=3, lang="pt", status="new")
    set_fit(conn, a, 81, {"score": 81, "summary": "Strong GIS match", "strengths": ["QGIS"], "gaps": ["Remote sensing"]})
    return a, b


@pytest.fixture
def client(data_dir, seeded):
    return TestClient(create_app(data_dir))


def test_root_redirects_to_new_jobs(client):
    r = client.get("/")
    assert r.status_code == 200 and str(r.url).endswith("/jobs?status=new")


def test_jobs_list_shows_new_jobs_with_scores(client):
    r = client.get("/jobs?status=new")
    assert r.status_code == 200 and "GIS Analyst" in r.text and "81" in r.text and "Strong GIS match" in r.text
    assert "Analista Ambiental" in r.text and "Geoespacial e dados" in r.text


def test_jobs_track_filter(client):
    r = client.get("/jobs?status=new&track=env-consulting")
    assert "Analista Ambiental" in r.text and "GIS Analyst" not in r.text


def test_status_change_moves_job(client, seeded):
    r = client.post(f"/jobs/{seeded[0]}/status", data={"status": "selected"})
    assert r.status_code == 200
    assert "GIS Analyst" in client.get("/jobs?status=selected").text
    assert "GIS Analyst" not in client.get("/jobs?status=new").text


def test_status_change_rejects_unknown(client, seeded):
    assert client.post(f"/jobs/{seeded[0]}/status", data={"status": "x"}).status_code == 400


def test_job_detail_shows_fit(client, seeded):
    r = client.get(f"/jobs/{seeded[0]}")
    assert "QGIS daily" in r.text and "Remote sensing" in r.text and "Avaliar com Claude" in r.text


def test_job_detail_404(client):
    assert client.get("/jobs/999").status_code == 404


def test_score_shows_llm_error(client, seeded, monkeypatch):
    class Down:
        def complete(self, prompt, json_schema=None):
            raise LLMError("claude CLI not found")
    monkeypatch.setattr("gmaj.web.app.get_llm", lambda *a: Down())
    r = client.post(f"/jobs/{seeded[1]}/score")
    assert r.status_code == 200 and "not found" in r.text


def test_score_saves_fit(client, seeded, monkeypatch, fake_llm_factory):
    llm = fake_llm_factory(['{"score": 64, "summary": "Bom encaixe", "strengths": [], "gaps": []}'])
    monkeypatch.setattr("gmaj.web.app.get_llm", lambda *a: llm)
    r = client.post(f"/jobs/{seeded[1]}/score")
    assert "64" in r.text and "Bom encaixe" in r.text


def test_profile_page_lists_unreviewed(client):
    r = client.get("/profile")
    assert "não revisadas" in r.text and "experiences[1].title" in r.text


def test_profile_save_rejects_invalid_yaml(client, data_dir):
    before = (data_dir / "search.yaml").read_text()
    for bad in ("tracks: []", "tracks: [unclosed"):
        r = client.post("/profile", data={"kind": "search", "content": bad})
        assert r.status_code == 200 and "erro" in r.text.lower()
        assert (data_dir / "search.yaml").read_text() == before


def test_profile_save_writes_valid_yaml(client, data_dir):
    content = (data_dir / "profile.yaml").read_text().replace("Ana Exemplo", "Ana Exemplo Silva")
    r = client.post("/profile", data={"kind": "profile", "content": content})
    assert r.status_code == 200 and "Ana Exemplo Silva" in (data_dir / "profile.yaml").read_text()


def test_import_text_creates_job(client):
    r = client.post("/import/text", data={"title": "Geotécnico", "company": "Acme", "description": "taludes", "url": ""})
    assert r.status_code == 200 and "Geotécnico" in r.text
    assert "Geotécnico" in client.get("/jobs?status=new").text


def test_import_url_without_jobposting_asks_for_text(client, monkeypatch):
    monkeypatch.setattr("gmaj.web.app.fetch_job", lambda url, c: None)
    r = client.post("/import/url", data={"url": "https://www.linkedin.com/jobs/view/1"})
    assert "Cole o texto" in r.text


def test_collect_button_starts_background_run(client, monkeypatch):
    calls = []
    monkeypatch.setattr("gmaj.web.app.run_collect", lambda d: calls.append(d))
    r = client.post("/collect")
    assert r.status_code == 200 and calls and "Buscando vagas" in r.text


def test_missing_profile_shows_banner(data_dir):
    r = TestClient(create_app(data_dir)).get("/jobs?status=new")
    assert r.status_code == 200 and "gmaj init" in r.text

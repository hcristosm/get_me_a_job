"""Regression tests for the final review findings."""
import json
import shutil

import httpx
import pytest
from fastapi.testclient import TestClient

from conftest import EX, FakeLLM, make_track, mock_client
from gmaj.config import Settings
from gmaj.db import connect, get_job, list_jobs, set_triage, upsert_job, jobs_needing_fit
from gmaj.jobs import Job
from gmaj.pipeline import collect, triage_and_store
from gmaj.profile import SearchConfig
from gmaj.triage import passes_filters
from gmaj.web.app import create_app


@pytest.fixture
def initialized(data_dir):
    shutil.copy(EX / "profile.example.yaml", data_dir / "profile.yaml")
    shutil.copy(EX / "search.example.yaml", data_dir / "search.yaml")
    return data_dir


# C1: CSRF / DNS rebinding
def test_rejects_foreign_host_header(initialized):
    c = TestClient(create_app(initialized), base_url="http://evil.example")
    assert c.get("/profile").status_code == 400


def test_rejects_cross_site_post(initialized):
    c = TestClient(create_app(initialized), base_url="http://127.0.0.1:8765")
    before = (initialized / "profile.yaml").read_text()
    for headers in ({"origin": "https://evil.example"}, {"sec-fetch-site": "cross-site"}):
        r = c.post("/profile", data={"kind": "profile", "content": before}, headers=headers)
        assert r.status_code == 403
    assert c.post("/collect", headers={"origin": "https://evil.example"}).status_code == 403


def test_same_origin_post_allowed(initialized):
    c = TestClient(create_app(initialized), base_url="http://127.0.0.1:8765")
    r = c.post("/import/text", data={"title": "T", "company": "C", "description": "d"},
               headers={"origin": "http://127.0.0.1:8765", "sec-fetch-site": "same-origin"})
    assert r.status_code == 200


# I2: null fields from a source must not crash the collect
def test_job_coerces_null_text_fields():
    j = Job("x", "1", "https://x/1", None, None, None, None)
    assert (j.title, j.company, j.location, j.description) == ("", "", "", "")


def test_non_http_job_urls_are_never_linked(initialized):
    conn = connect(initialized / "jobs.sqlite")
    jid = upsert_job(conn, Job("x", "1", "javascript:alert(1)", "GIS Evil", "C"))
    set_triage(conn, jid, track_id="gis-data", keyword_score=5, lang="en", status="new")
    c = TestClient(create_app(initialized), base_url="http://127.0.0.1:8765")
    for page in ("/jobs?status=new", f"/jobs/{jid}"):
        r = c.get(page)
        assert "GIS Evil" in r.text and "javascript:" not in r.text


def test_collect_survives_bad_job_and_runs_other_sources(tmp_path, example_profile, board_client, monkeypatch):
    from gmaj import sources

    def bad(track, client, settings):
        return [Job.__new__(Job)]  # a malformed job object
    monkeypatch.setitem(sources.SOURCES, "bad", bad)
    search = SearchConfig(tracks=[dict(id="s", name="S", keywords={"account executive": 2}, sources=["bad", "greenhouse"],
                                       companies={"greenhouse": ["planetlabs"]})])
    rep = collect(connect(tmp_path / "j.sqlite"), search, example_profile, Settings(), board_client, None, tmp_path / "l")
    assert rep.new == 2 and any(e.startswith("bad/s") for e in rep.errors)


# I3: background collect failures reach the UI
def test_safe_run_collect_records_failure(initialized):
    (initialized / "settings.yaml").write_text("llm: {scoring: nope}")
    from gmaj.pipeline import safe_run_collect
    safe_run_collect(initialized)
    rep = json.loads((initialized / "last_collect.json").read_text())
    assert rep["errors"] and "nope" in rep["errors"][0]


# I4: remote / location filters
def test_location_remote_inferred_and_word_boundaries():
    t = make_track(locations=["sp", "campinas"], remote=["remote", "hybrid"])
    assert passes_filters(Job("x", "1", "https://u", "GIS", "A", location="Remote"), t)
    assert passes_filters(Job("x", "1", "https://u", "GIS", "A", location="Remoto - Brasil"), t)
    assert not passes_filters(Job("x", "1", "https://u", "GIS", "A", location="Madrid, Spain"), t)
    assert passes_filters(Job("x", "1", "https://u", "GIS", "A", location="Campinas, SP"), t)


# I5: LinkedIn is never fetched, even through redirects
def test_client_blocks_linkedin_redirects():
    from gmaj.sources import make_client
    from gmaj.sources.url_import import fetch_job
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.host == "lnk.example":
            return httpx.Response(302, headers={"location": "https://www.linkedin.com/jobs/view/1"})
        return httpx.Response(200, text="<html></html>")
    client = make_client(Settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPError):
        fetch_job("https://lnk.example/x", client)
    for url in ("https://lnkd.in/abc", "https://linkedin.com./jobs/1"):
        with pytest.raises(httpx.HTTPError):
            client.get(url)
    assert not any("linkedin" in u or "lnkd.in" in u for u in seen)


# I6: a broken YAML on disk must not break every page
def test_broken_search_yaml_shows_banner_and_profile_still_works(initialized, capsys):
    (initialized / "search.yaml").write_text("tracks: [unclosed")
    c = TestClient(create_app(initialized), base_url="http://127.0.0.1:8765")
    r = c.get("/jobs?status=new")
    assert r.status_code == 200 and "search.yaml" in r.text
    r = c.get("/profile")
    assert r.status_code == 200 and "tracks: [unclosed" in r.text
    from gmaj.cli import main
    assert main(["collect"]) == 1 and "search.yaml" in capsys.readouterr().out


# I7: scoring must not stall
def test_scoring_falls_back_when_track_was_removed(tmp_path, example_profile, board_client):
    conn = connect(tmp_path / "j.sqlite")
    jid = upsert_job(conn, Job("x", "1", "https://x/1", "GIS Analyst", "A"))
    set_triage(conn, jid, track_id="deleted-track", keyword_score=5, lang="en", status="new")
    search = SearchConfig(tracks=[dict(id="gis", name="GIS", keywords={"gis": 1}, sources=[])])
    fit = '{"score": 50, "summary": "s", "strengths": [], "gaps": []}'
    rep = collect(conn, search, example_profile, Settings(), board_client, FakeLLM([fit]), tmp_path / "l")
    assert rep.scored == 1


def test_unparseable_jobs_go_down_the_queue_and_stop_after_3(tmp_path, example_profile, board_client):
    conn = connect(tmp_path / "j.sqlite")
    a = upsert_job(conn, Job("x", "1", "https://x/1", "GIS A", "A"))
    b = upsert_job(conn, Job("x", "2", "https://x/2", "GIS B", "B"))
    set_triage(conn, a, track_id="gis", keyword_score=9, lang="en", status="new")
    set_triage(conn, b, track_id="gis", keyword_score=1, lang="en", status="new")
    search = SearchConfig(tracks=[dict(id="gis", name="GIS", keywords={"gis": 1}, sources=[])])
    s = Settings(max_scored_per_run=1)
    for _ in range(3):
        collect(conn, search, example_profile, s, board_client, FakeLLM(["garbage"]), tmp_path / "l")
    ids = [r["id"] for r in jobs_needing_fit(conn, 10)]
    assert ids[0] == b
    for _ in range(3):
        collect(conn, search, example_profile, s, board_client, FakeLLM(["garbage"]), tmp_path / "l")
    assert jobs_needing_fit(conn, 10) == []


# I8: filtered jobs are re-triaged when seen again
def test_filtered_job_is_retriaged_when_seen_again(tmp_path):
    conn = connect(tmp_path / "j.sqlite")
    strict = SearchConfig(tracks=[dict(id="t", name="T", keywords={"gis": 1}, sources=[], remote=["remote"])])
    onsite = Job("x", "1", "https://x/1", "GIS Analyst", "Acme", remote="onsite")
    jid = triage_and_store(conn, onsite, strict)
    assert get_job(conn, jid)["status"] == "filtered"
    remote = Job("x", "2", "https://x/2", "GIS Analyst", "Acme", remote="remote")
    triage_and_store(conn, remote, strict)
    row = get_job(conn, jid)
    assert row["status"] == "new" and row["url"] == "https://x/2" and len(list_jobs(conn, "new")) == 1


def test_retriage_never_touches_user_decisions(tmp_path):
    from gmaj.db import set_status
    conn = connect(tmp_path / "j.sqlite")
    search = SearchConfig(tracks=[dict(id="t", name="T", keywords={"gis": 1}, sources=[])])
    jid = triage_and_store(conn, Job("x", "1", "https://x/1", "GIS Analyst", "Acme"), search)
    set_status(conn, jid, "discarded")
    triage_and_store(conn, Job("x", "2", "https://x/2", "GIS Analyst", "Acme"), search)
    assert get_job(conn, jid)["status"] == "discarded" and get_job(conn, jid)["url"] == "https://x/1"

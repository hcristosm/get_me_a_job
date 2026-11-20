import fcntl
import json

import httpx
import pytest

from conftest import FakeLLM
from gmaj.config import Settings
from gmaj.db import connect, list_jobs
from gmaj.pipeline import collect, triage_and_store
from gmaj.jobs import Job
from gmaj.profile import SearchConfig

FIT = '{"score": 70, "summary": "ok", "strengths": [], "gaps": []}'


def _search(sources=("greenhouse",), **track):
    t = dict(id="sales", name="Sales", keywords={"account executive": 2}, exclude=["france"],
             sources=list(sources), companies={"greenhouse": ["planetlabs"]})
    return SearchConfig(tracks=[{**t, **track}])


@pytest.fixture
def conn(tmp_path):
    return connect(tmp_path / "j.sqlite")


def test_collect_filters_unmatched(conn, tmp_path, example_profile, board_client):
    rep = collect(conn, _search(), example_profile, Settings(), board_client, None, tmp_path / "l")
    assert (rep.fetched, rep.new, rep.kept) == (2, 2, 1)
    assert [r["title"] for r in list_jobs(conn, "new")] == ["Account Executive, Defence & Intelligence"]
    assert len(list_jobs(conn, "filtered")) == 1
    assert list_jobs(conn, "new")[0]["track_id"] == "sales" and list_jobs(conn, "new")[0]["lang"] == "en"


def test_collect_survives_broken_source(conn, tmp_path, example_profile, board_client, monkeypatch):
    def broken(track, client, settings):
        raise httpx.ConnectError("boom")
    monkeypatch.setitem(__import__("gmaj.sources").sources.SOURCES, "broken", broken)
    rep = collect(conn, _search(sources=("greenhouse", "broken", "nope")), example_profile, Settings(),
                  board_client, None, tmp_path / "l")
    assert rep.new == 2 and any(e.startswith("broken/sales") for e in rep.errors)
    assert any(e.startswith("nope/sales") for e in rep.errors)
    assert "broken" in (tmp_path / "last_collect.json").read_text()


def test_collect_without_llm_keeps_keyword_scores(conn, tmp_path, example_profile, board_client):
    rep = collect(conn, _search(), example_profile, Settings(), board_client, None, tmp_path / "l")
    rows = list_jobs(conn, "new")
    assert rows and all(r["fit_score"] is None and r["keyword_score"] > 0 for r in rows) and rep.scored == 0


def test_collect_scores_up_to_limit(conn, tmp_path, example_profile, board_client):
    search = _search(exclude=[])
    rep = collect(conn, search, example_profile, Settings(max_scored_per_run=1), board_client, FakeLLM([FIT]),
                  tmp_path / "l")
    assert rep.scored == 1 and [r["fit_score"] for r in list_jobs(conn, "new")] == [70, None]


def test_collect_bad_llm_answer_leaves_job_for_next_run(conn, tmp_path, example_profile, board_client):
    rep = collect(conn, _search(), example_profile, Settings(), board_client, FakeLLM(["garbage"]), tmp_path / "l")
    assert rep.scored == 0 and list_jobs(conn, "new")[0]["fit_score"] is None


def test_collect_lock_skips_second_run(conn, tmp_path, example_profile, board_client):
    with open(tmp_path / "l", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rep = collect(conn, _search(), example_profile, Settings(), board_client, None, tmp_path / "l")
    assert rep.skipped and board_client.requests == []


def test_second_collect_adds_nothing(conn, tmp_path, example_profile, board_client):
    collect(conn, _search(), example_profile, Settings(), board_client, None, tmp_path / "l")
    rep = collect(conn, _search(), example_profile, Settings(), board_client, None, tmp_path / "l")
    assert rep.new == 0 and rep.fetched == 2
    assert json.loads((tmp_path / "last_collect.json").read_text())["new"] == 0


def test_triage_and_store_keeps_unmatched_import_as_new(conn):
    jid = triage_and_store(conn, Job("manual", "x", "manual:x", "Cozinheiro", "Restaurante"), _search(), force_new=True)
    rows = list_jobs(conn, "new")
    assert [r["id"] for r in rows] == [jid] and rows[0]["lang"] in ("pt", "en")

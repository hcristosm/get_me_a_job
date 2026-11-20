import pytest

from gmaj.db import connect, get_job, list_jobs, row_to_job, set_fit, set_status, set_triage, upsert_job, jobs_needing_fit
from gmaj.jobs import Job


def _job(**kw):
    base = dict(source="greenhouse", external_id="1", url="https://x/1", title="GIS Analyst", company="Acme")
    return Job(**{**base, **kw})


def test_upsert_dedups_and_keeps_status(tmp_path):
    conn = connect(tmp_path / "j.sqlite")
    jid = upsert_job(conn, _job())
    set_status(conn, jid, "discarded")
    assert upsert_job(conn, _job()) is None
    assert upsert_job(conn, _job(source="lever", url="https://y/7")) is None
    assert get_job(conn, jid)["status"] == "discarded"


def test_set_status_rejects_unknown(tmp_path):
    conn = connect(tmp_path / "j.sqlite")
    jid = upsert_job(conn, _job())
    with pytest.raises(ValueError):
        set_status(conn, jid, "bogus")


def test_list_jobs_orders_by_fit_then_keyword(tmp_path):
    conn = connect(tmp_path / "j.sqlite")
    a = upsert_job(conn, _job(url="u/a", title="A"))
    b = upsert_job(conn, _job(url="u/b", title="B"))
    set_triage(conn, a, track_id="t", keyword_score=9, lang="en", status="new")
    set_triage(conn, b, track_id="t", keyword_score=1, lang="en", status="new")
    set_fit(conn, b, 80, {"score": 80})
    assert [r["id"] for r in list_jobs(conn, "new")] == [b, a]
    assert [r["id"] for r in list_jobs(conn, "new", track_id="other")] == []


def test_jobs_needing_fit_and_row_to_job(tmp_path):
    conn = connect(tmp_path / "j.sqlite")
    a = upsert_job(conn, _job(url="u/a", title="A", description="d"))
    set_triage(conn, a, track_id="t", keyword_score=2, lang="pt", status="new")
    rows = jobs_needing_fit(conn, 10)
    assert [r["id"] for r in rows] == [a]
    j = row_to_job(rows[0])
    assert j.title == "A" and j.description == "d" and j.url == "u/a"
    set_fit(conn, a, 50, {"score": 50})
    assert jobs_needing_fit(conn, 10) == []

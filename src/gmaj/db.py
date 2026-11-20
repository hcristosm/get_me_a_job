import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from gmaj.jobs import Job, dedup_key

STATUSES = ("new", "selected", "applied", "discarded", "filtered")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  source TEXT, external_id TEXT, url TEXT UNIQUE, dedup_key TEXT,
  title TEXT, company TEXT, location TEXT, remote TEXT, description TEXT,
  posted_at TEXT, fetched_at TEXT, lang TEXT, track_id TEXT,
  keyword_score REAL, fit_score INTEGER, fit_json TEXT,
  status TEXT NOT NULL DEFAULT 'new', updated_at TEXT
);
CREATE INDEX IF NOT EXISTS jobs_dedup ON jobs(dedup_key);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def upsert_job(conn: sqlite3.Connection, job: Job) -> int | None:
    key = dedup_key(job)
    if conn.execute("SELECT 1 FROM jobs WHERE url = ? OR dedup_key = ?", (job.url, key)).fetchone():
        return None
    cur = conn.execute(
        "INSERT INTO jobs (source, external_id, url, dedup_key, title, company, location, remote,"
        " description, posted_at, fetched_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (job.source, job.external_id, job.url, key, job.title, job.company, job.location, job.remote,
         job.description, job.posted_at, _now(), _now()),
    )
    conn.commit()
    return cur.lastrowid


def set_triage(conn, job_id: int, *, track_id: str | None, keyword_score: float, lang: str, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"unknown status: {status}")
    conn.execute(
        "UPDATE jobs SET track_id=?, keyword_score=?, lang=?, status=?, updated_at=? WHERE id=?",
        (track_id, keyword_score, lang, status, _now(), job_id),
    )
    conn.commit()


def set_fit(conn, job_id: int, score: int, fit: dict) -> None:
    conn.execute("UPDATE jobs SET fit_score=?, fit_json=?, updated_at=? WHERE id=?",
                 (score, json.dumps(fit, ensure_ascii=False), _now(), job_id))
    conn.commit()


def set_status(conn, job_id: int, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"unknown status: {status}")
    conn.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (status, _now(), job_id))
    conn.commit()


def get_job(conn, job_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()


def list_jobs(conn, status: str, track_id: str | None = None, limit: int = 200) -> list[sqlite3.Row]:
    sql = "SELECT * FROM jobs WHERE status=?"
    args: list = [status]
    if track_id:
        sql += " AND track_id=?"
        args.append(track_id)
    sql += " ORDER BY COALESCE(fit_score, -1) DESC, keyword_score DESC, posted_at DESC LIMIT ?"
    return conn.execute(sql, (*args, limit)).fetchall()


def jobs_needing_fit(conn, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM jobs WHERE status='new' AND fit_score IS NULL ORDER BY keyword_score DESC LIMIT ?",
        (limit,),
    ).fetchall()


def row_to_job(row: sqlite3.Row) -> Job:
    return Job(source=row["source"], external_id=row["external_id"], url=row["url"], title=row["title"],
               company=row["company"], location=row["location"] or "", description=row["description"] or "",
               remote=row["remote"], posted_at=row["posted_at"])

import fcntl
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

from gmaj.config import Settings
from gmaj.db import jobs_needing_fit, row_to_job, set_fit, set_triage, upsert_job
from gmaj.jobs import Job
from gmaj.llm import LLM, LLMError
from gmaj.profile import Profile, SearchConfig
from gmaj.triage import best_track, detect_lang, keyword_score, score_fit


@dataclass
class CollectReport:
    fetched: int = 0
    new: int = 0
    kept: int = 0
    scored: int = 0
    errors: list[str] = field(default_factory=list)
    skipped: bool = False


def triage_and_store(conn: sqlite3.Connection, job: Job, search: SearchConfig, force_new: bool = False) -> int | None:
    """Store a job and triage it against all tracks. force_new keeps an unmatched job visible (manual imports)."""
    jid = upsert_job(conn, job)
    if jid is None:
        return None
    tracks = search.resolved_tracks()
    match = best_track(job, tracks)
    track, score = match or max(((t, keyword_score(job, t)) for t in tracks), key=lambda x: x[1])
    status = "new" if match or force_new else "filtered"
    set_triage(conn, jid, track_id=track.id, keyword_score=score,
               lang=detect_lang(job.title + " " + job.description), status=status)
    return jid


def collect(conn: sqlite3.Connection, search: SearchConfig, profile: Profile, settings: Settings,
            client: httpx.Client, scoring_llm: LLM | None, lock_path: Path) -> CollectReport:
    from gmaj.sources import SOURCES
    with open(lock_path, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return CollectReport(skipped=True)
        rep = CollectReport()
        tracks = search.resolved_tracks()
        for track in tracks:
            for source in track.sources:
                try:
                    jobs = SOURCES[source](track, client, settings)
                except KeyError:
                    rep.errors.append(f"{source}/{track.id}: unknown source")
                    continue
                except Exception as e:  # one broken source must not stop the others
                    rep.errors.append(f"{source}/{track.id}: {type(e).__name__}: {e}")
                    continue
                rep.fetched += len(jobs)
                for job in jobs:
                    jid = triage_and_store(conn, job, search)
                    if jid is not None:
                        rep.new += 1
                        rep.kept += conn.execute("SELECT status='new' FROM jobs WHERE id=?", (jid,)).fetchone()[0]
        if scoring_llm is not None:
            by_id = {t.id: t for t in tracks}
            for row in jobs_needing_fit(conn, settings.max_scored_per_run):
                track = by_id.get(row["track_id"])
                try:
                    fit = track and score_fit(row_to_job(row), track, profile, row["lang"] or "en", scoring_llm)
                except LLMError as e:  # backend down: stop scoring, keep keyword scores, retry next run
                    rep.errors.append(f"scoring: {e}")
                    break
                if fit:
                    set_fit(conn, row["id"], fit["score"], fit)
                    rep.scored += 1
        report = {**asdict(rep), "finished_at": datetime.now(UTC).isoformat()}
        (lock_path.parent / "last_collect.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        return rep


class NotInitialized(Exception):
    pass


def load_user_files(d: Path) -> tuple[Profile, SearchConfig]:
    from gmaj.profile import load_profile, load_search
    if not (d / "profile.yaml").exists() or not (d / "search.yaml").exists():
        raise NotInitialized("no profile yet: run 'gmaj init --cv <your_cv.pdf>' first")
    return load_profile(d / "profile.yaml"), load_search(d / "search.yaml")


def run_collect(d: Path | None = None) -> CollectReport:
    """Collect with the user's files and settings (used by the CLI and the web button)."""
    from gmaj import sources
    from gmaj.config import data_dir, load_settings
    from gmaj.db import connect
    from gmaj.llm import get_llm
    from gmaj.llm.ollama import OllamaLLM
    d = d or data_dir()
    profile, search = load_user_files(d)
    settings = load_settings(d)
    llm = get_llm("scoring", settings)
    if isinstance(llm, OllamaLLM) and not llm.is_available():
        llm = None  # keyword scores only; jobs get a fit score on a later run
    with sources.make_client(settings) as client:
        return collect(connect(d / "jobs.sqlite"), search, profile, settings, client, llm, d / "collect.lock")


def is_collecting(lock_path: Path) -> bool:
    if not lock_path.exists():
        return False
    with open(lock_path, "a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(f, fcntl.LOCK_UN)
        return False

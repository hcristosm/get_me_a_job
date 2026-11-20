import fcntl
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

from gmaj.config import Settings
from gmaj.db import find_existing, jobs_needing_fit, mark_fit_failed, replace_job_data, row_to_job, set_fit, set_triage, upsert_job
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
    """Store a job and triage it against all tracks. force_new keeps an unmatched job visible (manual imports).

    Returns the id of a newly stored job, else None. A duplicate of a job that was filtered out is
    re-triaged with the fresh data (the posting or the search config may have changed); duplicates of
    jobs the user already acted on are left alone.
    """
    jid = upsert_job(conn, job)
    if jid is None:
        old = find_existing(conn, job)
        if old is None or old["status"] != "filtered":
            return None
        replace_job_data(conn, old["id"], job)
        _triage(conn, old["id"], job, search, force_new)
        return None
    _triage(conn, jid, job, search, force_new)
    return jid


def _triage(conn, jid: int, job: Job, search: SearchConfig, force_new: bool) -> None:
    tracks = search.resolved_tracks()
    match = best_track(job, tracks)
    track, score = match or max(((t, keyword_score(job, t)) for t in tracks), key=lambda x: x[1])
    status = "new" if match or force_new else "filtered"
    set_triage(conn, jid, track_id=track.id, keyword_score=score,
               lang=detect_lang(job.title + " " + job.description), status=status)


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
                    try:
                        jid = triage_and_store(conn, job, search)
                    except Exception as e:  # one malformed job must not stop the run
                        rep.errors.append(f"{source}/{track.id}: bad job: {type(e).__name__}: {e}")
                        continue
                    if jid is not None:
                        rep.new += 1
                        rep.kept += conn.execute("SELECT status='new' FROM jobs WHERE id=?", (jid,)).fetchone()[0]
        if scoring_llm is not None:
            by_id = {t.id: t for t in tracks}
            for row in jobs_needing_fit(conn, settings.max_scored_per_run):
                job = row_to_job(row)
                track = by_id.get(row["track_id"]) or (best_track(job, tracks) or (tracks[0],))[0]
                try:
                    fit = score_fit(job, track, profile, row["lang"] or "en", scoring_llm)
                except LLMError as e:  # backend down: stop scoring, keep keyword scores, retry next run
                    rep.errors.append(f"scoring: {e}")
                    break
                if fit:
                    set_fit(conn, row["id"], fit["score"], fit)
                    rep.scored += 1
                else:
                    mark_fit_failed(conn, row["id"])  # goes down the queue; dropped after a few tries
        write_report(lock_path.parent, rep)
        return rep


def write_report(d: Path, rep: CollectReport) -> None:
    report = {**asdict(rep), "finished_at": datetime.now(UTC).isoformat()}
    tmp = d / "last_collect.json.tmp"
    tmp.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    tmp.replace(d / "last_collect.json")


class ConfigError(Exception):
    pass


class NotInitialized(ConfigError):
    pass


def load_user_files(d: Path) -> tuple[Profile, SearchConfig]:
    import yaml
    from pydantic import ValidationError

    from gmaj.profile import load_profile, load_search
    if not (d / "profile.yaml").exists() or not (d / "search.yaml").exists():
        raise NotInitialized("no profile yet: run 'gmaj init --cv <your_cv.pdf>' first")
    out = []
    for name, load in (("profile.yaml", load_profile), ("search.yaml", load_search)):
        try:
            out.append(load(d / name))
        except (yaml.YAMLError, ValidationError) as e:
            raise ConfigError(f"{name} has an error: {e}") from e
    return out[0], out[1]


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


def safe_run_collect(d: Path) -> None:
    """run_collect for the web button: any failure is written to last_collect.json so the UI shows it."""
    try:
        run_collect(d)
    except Exception as e:
        write_report(d, CollectReport(errors=[f"{type(e).__name__}: {e}"]))


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

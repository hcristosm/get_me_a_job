import httpx

from gmaj.config import Settings
from gmaj.jobs import Job, html_to_text
from gmaj.profile import Track

# Public JSON used by https://portal.gupy.io/job-search (verified 2026-11-19).
URL = "https://portal.gupy.io/api/job-search/jobs"


def fetch(track: Track, client: httpx.Client, settings: Settings) -> list[Job]:
    from gmaj.sources import remote_kind, search_terms
    jobs: dict[str, Job] = {}
    for q in search_terms(track):
        r = client.get(URL, params={"jobName": q, "limit": 50, "offset": 0})
        r.raise_for_status()
        for j in r.json().get("data", []):
            jobs.setdefault(str(j["id"]), Job(
                source="gupy", external_id=str(j["id"]), url=j["jobUrl"], title=j["name"].strip(),
                company=j.get("careerPageName", ""),
                location=", ".join(filter(None, [j.get("city"), j.get("state")])),
                description=html_to_text(j.get("description", "")),
                remote=remote_kind(j.get("workplaceType")), posted_at=j.get("publishedDate"),
            ))
    return list(jobs.values())

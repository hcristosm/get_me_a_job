import httpx

from gmaj.config import Settings
from gmaj.jobs import Job
from gmaj.profile import Track

URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def fetch(track: Track, client: httpx.Client, settings: Settings) -> list[Job]:
    from gmaj.sources import remote_kind
    jobs = []
    for slug in track.companies.get("ashby", []):
        r = client.get(URL.format(slug=slug))
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            jobs.append(Job(
                source="ashby", external_id=j["id"], url=j["jobUrl"], title=j["title"].strip(), company=slug,
                location=j.get("location") or "", description=j.get("descriptionPlain") or "",
                remote=remote_kind(j.get("workplaceType")) or ("remote" if j.get("isRemote") else None),
                posted_at=j.get("publishedAt"),
            ))
    return jobs

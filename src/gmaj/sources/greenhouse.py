import httpx

from gmaj.config import Settings
from gmaj.jobs import Job, html_to_text
from gmaj.profile import Track

URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


def fetch(track: Track, client: httpx.Client, settings: Settings) -> list[Job]:
    jobs = []
    for slug in track.companies.get("greenhouse", []):
        r = client.get(URL.format(slug=slug))
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            jobs.append(Job(
                source="greenhouse", external_id=str(j["id"]), url=j["absolute_url"], title=j["title"],
                company=j.get("company_name") or slug, location=(j.get("location") or {}).get("name", ""),
                description=html_to_text(j.get("content", "")),
                posted_at=j.get("first_published") or j.get("updated_at"),
            ))
    return jobs

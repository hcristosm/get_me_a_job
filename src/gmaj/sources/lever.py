from datetime import UTC, datetime

import httpx

from gmaj.config import Settings
from gmaj.jobs import Job
from gmaj.profile import Track

URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


def fetch(track: Track, client: httpx.Client, settings: Settings) -> list[Job]:
    from gmaj.sources import remote_kind
    jobs = []
    for slug in track.companies.get("lever", []):
        r = client.get(URL.format(slug=slug))
        r.raise_for_status()
        for j in r.json():
            created = j.get("createdAt")
            jobs.append(Job(
                source="lever", external_id=j["id"], url=j["hostedUrl"], title=j["text"], company=slug,
                location=(j.get("categories") or {}).get("location") or "",
                description="\n\n".join(filter(None, [j.get("descriptionPlain"), j.get("additionalPlain")])),
                remote=remote_kind(j.get("workplaceType")),
                posted_at=datetime.fromtimestamp(created / 1000, UTC).isoformat() if created else None,
            ))
    return jobs

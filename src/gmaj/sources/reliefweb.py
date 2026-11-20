import logging

import httpx

from gmaj.config import Settings
from gmaj.jobs import Job
from gmaj.profile import Track

# Needs an approved appname: https://apidoc.reliefweb.int/parameters#appname
URL = "https://api.reliefweb.int/v2/jobs"
FIELDS = ["title", "body", "url", "source.name", "country.name", "city.name", "date.created"]


def fetch(track: Track, client: httpx.Client, settings: Settings) -> list[Job]:
    from gmaj.sources import search_terms
    if not settings.reliefweb_appname:
        logging.warning("reliefweb skipped: set reliefweb_appname in settings.yaml")
        return []
    jobs: dict[str, Job] = {}
    for q in search_terms(track):
        body = {"query": {"value": q, "operator": "AND"}, "limit": 50, "sort": ["date.created:desc"],
                "fields": {"include": FIELDS}}
        r = client.post(URL, params={"appname": settings.reliefweb_appname}, json=body)
        r.raise_for_status()
        for item in r.json().get("data", []):
            f = item["fields"]
            names = lambda k: [x["name"] for x in f.get(k, [])]  # noqa: E731
            jobs.setdefault(str(item["id"]), Job(
                source="reliefweb", external_id=str(item["id"]), url=f["url"], title=f["title"],
                company=(names("source") or [""])[0], location=", ".join(names("city") + names("country")),
                description=f.get("body", ""), posted_at=(f.get("date") or {}).get("created"),
            ))
    return list(jobs.values())

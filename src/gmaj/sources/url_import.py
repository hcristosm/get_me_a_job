import hashlib
import json
import re
from urllib.parse import urlsplit

import httpx

from gmaj.jobs import Job, html_to_text

_LD = re.compile(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)


def _postings(data):
    items = data if isinstance(data, list) else [data]
    for it in items:
        if isinstance(it, dict):
            if "JobPosting" in (it.get("@type") if isinstance(it.get("@type"), list) else [it.get("@type")]):
                yield it
            yield from _postings(it.get("@graph", []))


def fetch_job(url: str, client: httpx.Client) -> Job | None:
    """Import one job page via its schema.org JobPosting JSON-LD. LinkedIn is never fetched."""
    host = urlsplit(url).hostname or ""
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        return None
    r = client.get(url)
    r.raise_for_status()
    for block in _LD.findall(r.text):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for p in _postings(data):
            loc = p.get("jobLocation") or {}
            addr = (loc[0] if isinstance(loc, list) and loc else loc).get("address") or {}
            org = p.get("hiringOrganization") or {}
            return Job(
                source="import", external_id=url, url=url, title=p.get("title", "").strip(),
                company=org.get("name", "") if isinstance(org, dict) else str(org),
                location=", ".join(filter(None, [addr.get("addressLocality"), addr.get("addressRegion")])),
                description=html_to_text(p.get("description", "")),
                remote="remote" if p.get("jobLocationType") == "TELECOMMUTE" else None,
                posted_at=p.get("datePosted"),
            )
    return None


def job_from_text(title: str, company: str, description: str, url: str = "") -> Job:
    eid = hashlib.sha1(description.encode("utf-8")).hexdigest()
    return Job(source="manual", external_id=eid, url=url or f"manual:{eid}", title=title.strip(),
               company=company.strip(), description=description.strip())

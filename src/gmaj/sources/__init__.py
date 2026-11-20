import time
from typing import Callable
from urllib.parse import urlsplit

import httpx

from gmaj.config import Settings
from gmaj.jobs import Job
from gmaj.profile import Track

from . import ashby, greenhouse, gupy, lever, reliefweb

Source = Callable[[Track, httpx.Client, Settings], list[Job]]

SOURCES: dict[str, Source] = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "reliefweb": reliefweb.fetch,
    "gupy": gupy.fetch,
}


BLOCKED_HOSTS = ("linkedin.com", "lnkd.in")


def is_blocked_host(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == b or host.endswith("." + b) for b in BLOCKED_HOSTS)


def make_client(settings: Settings, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    last: dict[str, float] = {}

    def throttle(request: httpx.Request) -> None:
        host = urlsplit(str(request.url)).hostname or ""
        if is_blocked_host(host):  # never scrape LinkedIn, also when a redirect points there
            raise httpx.RequestError(f"blocked host: {host}", request=request)
        # politeness: at most one request per second per host
        wait = last.get(host, 0) + 1.0 - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        last[host] = time.monotonic()

    return httpx.Client(headers={"User-Agent": settings.user_agent}, timeout=20, follow_redirects=True,
                        event_hooks={"request": [throttle]}, transport=transport)


def remote_kind(value: str | None) -> str | None:
    v = (value or "").lower().replace("-", "")
    return {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite", "inoffice": "onsite"}.get(v)


def search_terms(track: Track) -> list[str]:
    """Search terms for search-based sources: the track's queries, else its 3 heaviest keywords."""
    return track.queries or sorted(track.keywords, key=track.keywords.get, reverse=True)[:3]

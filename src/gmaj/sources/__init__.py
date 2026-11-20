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


def make_client(settings: Settings) -> httpx.Client:
    last: dict[str, float] = {}

    def throttle(request: httpx.Request) -> None:
        # politeness: at most one request per second per host
        host = urlsplit(str(request.url)).hostname or ""
        wait = last.get(host, 0) + 1.0 - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        last[host] = time.monotonic()

    return httpx.Client(headers={"User-Agent": settings.user_agent}, timeout=20, follow_redirects=True,
                        event_hooks={"request": [throttle]})


def remote_kind(value: str | None) -> str | None:
    v = (value or "").lower().replace("-", "")
    return {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite", "inoffice": "onsite"}.get(v)


def search_terms(track: Track) -> list[str]:
    """Search terms for search-based sources: the track's queries, else its 3 heaviest keywords."""
    return track.queries or sorted(track.keywords, key=track.keywords.get, reverse=True)[:3]

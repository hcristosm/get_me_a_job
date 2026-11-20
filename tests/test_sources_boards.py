import httpx
import pytest

from conftest import make_track
from gmaj.config import Settings


@pytest.mark.parametrize("src,slug", [("greenhouse", "planetlabs"), ("lever", "palantir"), ("ashby", "ramp")])
def test_board_source_maps_jobs(src, slug, board_client):
    from gmaj.sources import SOURCES
    track = make_track(sources=[src], companies={src: [slug]})
    jobs = SOURCES[src](track, board_client, Settings())
    assert len(jobs) == 2
    j = jobs[0]
    assert j.source == src and j.url.startswith("https://") and j.title and j.external_id and j.company
    assert j.description and "<" not in j.description


def test_lever_and_ashby_map_remote(board_client):
    from gmaj.sources import SOURCES
    lv = SOURCES["lever"](make_track(companies={"lever": ["palantir"]}), board_client, Settings())
    ab = SOURCES["ashby"](make_track(companies={"ashby": ["ramp"]}), board_client, Settings())
    assert [j.remote for j in lv] == ["hybrid", "onsite"]
    assert ab[0].remote == "hybrid" and ab[0].posted_at


def test_board_source_without_companies_returns_empty(board_client):
    from gmaj.sources import SOURCES
    assert SOURCES["greenhouse"](make_track(sources=["greenhouse"]), board_client, Settings()) == []


def test_board_source_raises_on_http_error(board_client):
    from gmaj.sources import SOURCES
    track = make_track(sources=["lever"], companies={"lever": ["does-not-exist"]})
    with pytest.raises(httpx.HTTPStatusError):
        SOURCES["lever"](track, board_client, Settings())


def test_make_client_sets_user_agent():
    from gmaj.sources import make_client
    assert make_client(Settings()).headers["user-agent"] == "get_me_a_job/0.1"

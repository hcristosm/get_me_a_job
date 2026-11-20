import json

import pytest

from conftest import FIX, make_track, mock_client
from gmaj.config import Settings
from gmaj.sources import SOURCES, search_terms


@pytest.fixture
def search_client():
    return mock_client({
        "https://api.reliefweb.int/v2/jobs": FIX / "reliefweb.json",
        "https://portal.gupy.io/api/job-search/jobs": FIX / "gupy.json",
    })


def test_search_terms_falls_back_to_top_keywords():
    t = make_track(keywords={"a": 1.0, "b": 3.0, "c": 2.0, "d": 0.5}, queries=[])
    assert search_terms(t) == ["b", "c", "a"]
    assert search_terms(make_track(queries=["x"])) == ["x"]


def test_reliefweb_without_appname_returns_empty(search_client):
    track = make_track(sources=["reliefweb"], queries=["landslide"])
    assert SOURCES["reliefweb"](track, search_client, Settings()) == []
    assert search_client.requests == []


def test_reliefweb_maps_jobs(search_client):
    track = make_track(sources=["reliefweb"], queries=["landslide"])
    jobs = SOURCES["reliefweb"](track, search_client, Settings(reliefweb_appname="test"))
    assert len(jobs) == 2
    assert jobs[0].company == "Example Relief Org" and jobs[0].location == "Kathmandu, Nepal"
    assert jobs[1].location == "Mozambique" and jobs[0].url.startswith("https://")
    body = json.loads(search_client.requests[0].content)
    assert body["query"]["value"] == "landslide"
    assert "appname=test" in str(search_client.requests[0].url)


def test_gupy_maps_jobs_and_dedupes_across_queries(search_client):
    track = make_track(sources=["gupy"], queries=["geólogo", "geologia"])
    jobs = SOURCES["gupy"](track, search_client, Settings())
    assert len(jobs) == 2 and len(search_client.requests) == 2
    j = jobs[0]
    assert j.source == "gupy" and j.company == "Atlantic Nickel" and j.location == "Belo Horizonte, Minas Gerais"
    assert j.remote == "onsite" and jobs[1].remote == "remote" and "&nbsp;" not in j.description
    assert search_client.requests[0].url.params["jobName"] == "geólogo"

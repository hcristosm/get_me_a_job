from conftest import FIX, mock_client
from gmaj.sources.url_import import fetch_job, job_from_text


def _client():
    return mock_client({"https://example.org/job/1": FIX / "jobposting.html",
                        "https://example.org/nojob": "<html><body>nothing</body></html>"})


def test_fetch_job_parses_jsonld():
    j = fetch_job("https://example.org/job/1", _client())
    assert (j.title, j.company, j.location, j.remote) == ("Geotechnical Engineer", "Acme Geo", "Campinas, SP", "remote")
    assert j.source == "import" and j.url == "https://example.org/job/1"
    assert "Slope stability" in j.description and "<" not in j.description


def test_fetch_job_without_jobposting_returns_none():
    assert fetch_job("https://example.org/nojob", _client()) is None


def test_fetch_job_refuses_linkedin():
    c = _client()
    assert fetch_job("https://www.linkedin.com/jobs/view/123", c) is None
    assert c.requests == []


def test_job_from_text_is_stable():
    a = job_from_text("T", "C", "desc")
    b = job_from_text("T", "C", "desc")
    assert a.external_id == b.external_id and a.url.startswith("manual:") and a.source == "manual"
    assert job_from_text("T", "C", "desc", url="https://x").url == "https://x"

import pytest


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAJ_DATA_DIR", str(tmp_path))
    return tmp_path


from pathlib import Path

import httpx

FIX = Path(__file__).parent / "fixtures"


def make_track(**kw):
    from gmaj.profile import Track
    base = dict(id="t1", name="T", keywords={"gis": 1.0}, sources=[])
    return Track(**{**base, **kw})


def mock_client(routes: dict[str, Path | str]) -> httpx.Client:
    """Client answering by URL prefix with a fixture file (404 otherwise); records requests."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        url = str(request.url)
        for prefix, body in routes.items():
            if url.startswith(prefix):
                text = body.read_text(encoding="utf-8") if isinstance(body, Path) else body
                ctype = "application/json" if text.lstrip()[:1] in "[{" else "text/html"
                return httpx.Response(200, text=text, headers={"content-type": ctype})
        return httpx.Response(404, text="not found")

    c = httpx.Client(transport=httpx.MockTransport(handler))
    c.requests = seen
    return c


@pytest.fixture
def board_client():
    return mock_client({
        "https://boards-api.greenhouse.io/v1/boards/planetlabs/": FIX / "greenhouse.json",
        "https://api.lever.co/v0/postings/palantir": FIX / "lever.json",
        "https://api.ashbyhq.com/posting-api/job-board/ramp": FIX / "ashby.json",
    })


EX = Path(__file__).parent.parent / "examples"


class FakeLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, prompt: str, json_schema: dict | None = None) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0)


@pytest.fixture
def fake_llm_factory():
    return FakeLLM


@pytest.fixture
def example_profile():
    from gmaj.profile import load_profile
    return load_profile(EX / "profile.example.yaml")


@pytest.fixture
def example_search():
    from gmaj.profile import load_search
    return load_search(EX / "search.example.yaml")

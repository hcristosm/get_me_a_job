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


def make_pdf(text: str) -> bytes:
    """Minimal valid one-page PDF with a single Helvetica text line (empty text → no text object)."""
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1") if text else b""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return out


@pytest.fixture
def example_profile_json(example_profile):
    return example_profile.model_dump_json()


@pytest.fixture
def example_search_json(example_search):
    return example_search.model_dump_json()

import html
import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass
class Job:
    source: str
    external_id: str
    url: str
    title: str
    company: str
    location: str = ""
    description: str = ""
    remote: str | None = None  # "remote" | "hybrid" | "onsite" | None
    posted_at: str | None = None  # ISO 8601

    def __post_init__(self):
        for f in ("title", "company", "location", "description"):
            setattr(self, f, getattr(self, f) or "")  # sources sometimes send null


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def dedup_key(job: Job) -> str:
    return normalize(job.company) + "|" + normalize(job.title)


_BLOCK = {"p", "br", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(raw: str) -> str:
    p = _Text()
    p.feed(html.unescape(raw or ""))
    p.close()
    text = "\n".join(line.strip() for line in "".join(p.parts).splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()

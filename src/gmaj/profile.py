from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Lang = Literal["pt", "en"]
Remote = Literal["remote", "hybrid", "onsite"]


class Text(BaseModel):
    """Free text with one variant per language; `auto` lists unreviewed machine translations."""
    model_config = ConfigDict(extra="allow")
    pt: str | None = None
    en: str | None = None
    auto: list[str] = []

    @model_validator(mode="after")
    def _one_language(self):
        if not any(v for k, v in self.variants().items()):
            raise ValueError("text needs at least one language")
        return self

    def variants(self) -> dict[str, str]:
        d = {"pt": self.pt, "en": self.en, **(self.model_extra or {})}
        return {k: v for k, v in d.items() if isinstance(v, str) and v}

    def get(self, lang: str) -> str:
        v = self.variants()
        return v.get(lang) or next(iter(v.values()))


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Bullet(_Strict):
    id: str
    text: Text


class Experience(_Strict):
    id: str
    title: Text
    org: str
    location: str = ""
    start: str
    end: str | None = None
    bullets: list[Bullet] = []


class Education(_Strict):
    id: str
    degree: Text
    institution: str
    start: str = ""
    end: str = ""
    notes: Text | None = None


class Project(_Strict):
    id: str
    name: str
    description: Text
    url: str = ""
    bullets: list[Bullet] = []


class Item(_Strict):
    id: str
    text: Text


class SkillGroup(_Strict):
    id: str
    name: Text
    items: list[str]


class Language(_Strict):
    name: str
    level: str


def _walk(obj, path: str):
    """Yield (path, Text) for every Text inside obj."""
    if isinstance(obj, Text):
        yield path, obj
    elif isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            yield from _walk(getattr(obj, name), f"{path}.{name}" if path else name)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}")


def _ids(obj):
    if isinstance(obj, BaseModel):
        if "id" in type(obj).model_fields:
            yield obj.id
        for name in type(obj).model_fields:
            yield from _ids(getattr(obj, name))
    elif isinstance(obj, list):
        for v in obj:
            yield from _ids(v)


class Profile(_Strict):
    name: str
    email: str
    phone: str = ""
    location: str = ""
    links: dict[str, str] = {}
    canonical_lang: Lang
    headline: Text
    summary: Text
    experiences: list[Experience]
    education: list[Education] = []
    projects: list[Project] = []
    awards: list[Item] = []
    courses: list[Item] = []
    skills: list[SkillGroup] = []
    languages: list[Language] = []
    answers: dict[str, Text] = {}

    @model_validator(mode="after")
    def _unique_ids(self):
        seen = set()
        for i in _ids(self):
            if i in seen:
                raise ValueError(f"duplicate id: {i}")
            seen.add(i)
        return self

    def unreviewed(self) -> list[str]:
        return [p for p, t in _walk(self, "") if t.auto]


class Track(_Strict):
    id: str
    name: str
    keywords: dict[str, float]
    queries: list[str] = []
    exclude: list[str] = []
    locations: list[str] | None = None
    remote: list[Remote] | None = None
    seniority: list[str] = []
    sources: list[str]
    companies: dict[str, list[str]] = {}
    emphasis: list[str] = []
    min_score: float = 1.0


class SearchConfig(_Strict):
    base_location: str = ""
    exclude: list[str] = []
    locations: list[str] = []
    remote: list[Remote] = ["remote", "hybrid", "onsite"]
    tracks: list[Track] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def _unique_track_ids(self):
        ids = [t.id for t in self.tracks]
        if len(ids) != len(set(ids)):
            raise ValueError("track ids must be unique")
        return self

    def resolved_tracks(self) -> list[Track]:
        return [
            t.model_copy(update={
                "locations": self.locations if t.locations is None else t.locations,
                "remote": self.remote if t.remote is None else t.remote,
                "exclude": self.exclude + t.exclude,
            })
            for t in self.tracks
        ]


def _load(model, path: Path):
    return model.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})


def _save(m: BaseModel, path: Path) -> None:
    data = m.model_dump(exclude_none=True)
    Path(path).write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_profile(path: Path) -> Profile:
    return _load(Profile, path)


def save_profile(p: Profile, path: Path) -> None:
    _save(p, path)


def load_search(path: Path) -> SearchConfig:
    return _load(SearchConfig, path)


def save_search(s: SearchConfig, path: Path) -> None:
    _save(s, path)


def profile_to_text(p: Profile, lang: str) -> str:
    """Plain-text profile in one language, each item tagged with its [id] for the LLM prompts."""
    out = [p.name, p.headline.get(lang), p.location, "", p.summary.get(lang), "", "EXPERIENCE"]
    for e in p.experiences:
        out.append(f"[{e.id}] {e.title.get(lang)} — {e.org} ({e.start} – {e.end or 'present'})")
        out += [f"  [{b.id}] {b.text.get(lang)}" for b in e.bullets]
    if p.projects:
        out.append("PROJECTS")
        for pr in p.projects:
            out.append(f"[{pr.id}] {pr.name}: {pr.description.get(lang)}")
            out += [f"  [{b.id}] {b.text.get(lang)}" for b in pr.bullets]
    if p.education:
        out.append("EDUCATION")
        out += [f"[{e.id}] {e.degree.get(lang)} — {e.institution} ({e.start}–{e.end})" for e in p.education]
    for label, items in (("AWARDS", p.awards), ("COURSES", p.courses)):
        if items:
            out.append(label)
            out += [f"[{i.id}] {i.text.get(lang)}" for i in items]
    if p.skills:
        out.append("SKILLS")
        out += [f"[{s.id}] {s.name.get(lang)}: {', '.join(s.items)}" for s in p.skills]
    if p.languages:
        out.append("LANGUAGES: " + ", ".join(f"{l.name} ({l.level})" for l in p.languages))
    return "\n".join(out)

import re
from importlib.resources import files
from typing import Literal

from gmaj.jobs import Job, normalize
from gmaj.llm import LLM, LLMError, parse_json
from gmaj.profile import Profile, Track, profile_to_text

_PT = set("de da do das dos em para com por uma um os as e ou que nao sao na no nas nos ao pela pelo "
          "vaga experiencia conhecimento requisitos atuar empresa sera voce nosso nossa".split())
_EN = set("the of and to in for with on is are we you our an be will this that or as at by "
          "experience requirements role team job work".split())

FIT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["score", "summary", "strengths", "gaps"],
}


def detect_lang(text: str) -> Literal["pt", "en"]:
    words = re.findall(r"[a-z]+", normalize(text))
    pt = sum(w in _PT for w in words)
    en = sum(w in _EN for w in words)
    return "pt" if pt > en else "en"


def _has(term: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(normalize(term))}\b", text) is not None


def keyword_score(job: Job, track: Track) -> float:
    title, body = normalize(job.title), normalize(job.description)
    return sum(w * (2 if _has(k, title) else 1 if _has(k, body) else 0) for k, w in track.keywords.items())


def passes_filters(job: Job, track: Track) -> bool:
    title = normalize(job.title)
    if any(_has(x, title) for x in track.exclude):
        return False
    if track.remote and job.remote and job.remote not in track.remote:
        return False
    loc = normalize(job.location)
    if track.locations and job.remote != "remote" and loc:
        return any(normalize(l) in loc for l in track.locations)
    return True


def best_track(job: Job, tracks: list[Track]) -> tuple[Track, float] | None:
    best = None
    for t in tracks:
        s = keyword_score(job, t)
        if s >= t.min_score and passes_filters(job, t) and (best is None or s > best[1]):
            best = (t, s)
    return best


def score_fit(job: Job, track: Track, profile: Profile, lang: str, llm: LLM) -> dict | None:
    prompt = files("gmaj.prompts").joinpath("fit_score.md").read_text(encoding="utf-8").format(
        track_name=track.name, profile=profile_to_text(profile, lang), job_title=job.title,
        job_company=job.company, job_description=job.description[:6000], lang=lang)
    answer = llm.complete(prompt, FIT_SCHEMA)  # backend errors propagate: callers decide
    try:
        d = parse_json(answer)
        return {"score": max(0, min(100, int(d["score"]))), "summary": str(d.get("summary", "")),
                "strengths": list(d.get("strengths", []))[:3], "gaps": list(d.get("gaps", []))[:3]}
    except (LLMError, KeyError, TypeError, ValueError):
        return None

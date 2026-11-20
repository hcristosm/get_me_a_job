import json
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ValidationError
from pypdf import PdfReader

from gmaj.config import data_dir, load_settings
from gmaj.llm import LLM, LLMError, get_llm, parse_json
from gmaj.profile import Profile, SearchConfig, profile_to_text, save_profile, save_search


def extract_pdf_text(path: Path) -> str:
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages).strip()
    if not text:
        raise ValueError("no text found in PDF (scanned image?)")
    return text


def _ask[M: BaseModel](llm: LLM, prompt: str, model: type[M]) -> M:
    """Ask for JSON matching `model`; on a bad answer, retry once with the error appended."""
    error = ""
    for _ in range(2):
        answer = llm.complete(prompt + error)  # backend errors (not logged in, offline) propagate as-is
        try:
            return model.model_validate(parse_json(answer))
        except (ValidationError, LLMError) as e:
            error = f"\n\nYour previous answer failed validation:\n{e}\nFix it and answer again with JSON only."
    raise LLMError(f"LLM answer still invalid after a retry: {error.strip()[:500]}")


def _prompt(name: str, **kw) -> str:
    return files("gmaj.prompts").joinpath(name).read_text(encoding="utf-8").format(**kw)


def build_profile(cv_text: str, llm: LLM) -> Profile:
    schema = json.dumps(Profile.model_json_schema())
    return _ask(llm, _prompt("onboard_profile.md", schema=schema, cv_text=cv_text), Profile)


def suggest_search(profile: Profile, llm: LLM) -> SearchConfig:
    from gmaj.sources import SOURCES
    prompt = _prompt("onboard_search.md", schema=json.dumps(SearchConfig.model_json_schema()),
                     sources=", ".join(SOURCES), profile=profile_to_text(profile, "en"))
    return _ask(llm, prompt, SearchConfig)


def init(cv: Path, force: bool = False) -> int:
    d = data_dir()
    targets = [d / "profile.yaml", d / "search.yaml"]
    if not force and any(t.exists() for t in targets):
        print(f"{d} already has a profile/search config. Use --force to overwrite.")
        return 1
    llm = get_llm("onboarding", load_settings())
    print("Reading CV and building your profile (this can take a minute)...")
    profile = build_profile(extract_pdf_text(cv), llm)
    save_profile(profile, targets[0])
    print("Suggesting search tracks...")
    save_search(suggest_search(profile, llm), targets[1])
    print(f"Wrote {targets[0]}\nWrote {targets[1]}")
    print(f"{len(profile.unreviewed())} machine-translated fields to review (run 'gmaj serve' → Perfil).")
    return 0

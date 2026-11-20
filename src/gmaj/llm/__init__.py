import json
import re
from typing import Protocol

from gmaj.config import Settings


class LLMError(Exception):
    pass


class LLM(Protocol):
    def complete(self, prompt: str, json_schema: dict | None = None) -> str: ...


def get_llm(task: str, settings: Settings) -> LLM:
    from gmaj.llm.claude_cli import ClaudeCLI
    from gmaj.llm.ollama import OllamaLLM
    name = getattr(settings.llm, task)
    s = settings.llm
    if name == "ollama":
        return OllamaLLM(s.ollama_url, s.ollama_model, s.timeout_s)
    if name == "claude_cli":
        return ClaudeCLI(s.claude_bin, s.timeout_s)
    raise ValueError(f"unknown LLM backend for {task}: {name!r} (use 'ollama' or 'claude_cli')")


def parse_json(text: str) -> dict:
    """Take the outermost {...} of an LLM answer, ignoring code fences and chatter."""
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        data = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        raise LLMError(f"LLM did not return a JSON object: {(text or '')[:200]!r}")
    return data

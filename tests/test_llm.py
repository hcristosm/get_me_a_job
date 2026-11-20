import pytest

from gmaj.config import Settings
from gmaj.llm import LLMError, get_llm, parse_json
from gmaj.llm.claude_cli import ClaudeCLI
from gmaj.llm.ollama import OllamaLLM


def test_get_llm_unknown_backend_raises():
    s = Settings()
    s.llm.scoring = "nope"
    with pytest.raises(ValueError):
        get_llm("scoring", s)


def test_get_llm_picks_backend_per_task():
    s = Settings()
    assert isinstance(get_llm("scoring", s), OllamaLLM)
    assert isinstance(get_llm("onboarding", s), ClaudeCLI)


def test_parse_json_strips_fences_and_prose():
    assert parse_json('Sure!\n```json\n{"a": {"b": 1}}\n```') == {"a": {"b": 1}}


def test_parse_json_raises_on_garbage():
    with pytest.raises(LLMError):
        parse_json("not json")


def test_claude_cli_missing_binary_raises_llmerror():
    with pytest.raises(LLMError, match="not found"):
        ClaudeCLI(bin="/nonexistent/claude", timeout=5).complete("hi")


def test_claude_cli_reads_result_field(tmp_path):
    fake = tmp_path / "claude"
    fake.write_text('#!/bin/sh\ncat > /dev/null\necho \'{"type":"result","is_error":false,"result":"hello"}\'\n')
    fake.chmod(0o755)
    assert ClaudeCLI(bin=str(fake), timeout=5).complete("hi") == "hello"


def test_claude_cli_error_result_raises(tmp_path):
    fake = tmp_path / "claude"
    fake.write_text('#!/bin/sh\ncat > /dev/null\necho \'{"is_error":true,"result":"limit reached"}\'\n')
    fake.chmod(0o755)
    with pytest.raises(LLMError, match="limit reached"):
        ClaudeCLI(bin=str(fake), timeout=5).complete("hi")


def test_ollama_unreachable_raises_llmerror():
    with pytest.raises(LLMError):
        OllamaLLM("http://127.0.0.1:9", "m", 2).complete("hi")
    assert OllamaLLM("http://127.0.0.1:9", "m", 2).is_available() is False

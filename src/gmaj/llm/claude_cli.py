import json
import subprocess
import tempfile

from gmaj.llm import LLMError

# One isolated, tool-less call per request: no history, no MCP servers, no saved session.
ARGS = ["-p", "--output-format", "json", "--tools", "", "--strict-mcp-config", "--no-session-persistence"]


class ClaudeCLI:
    def __init__(self, bin: str, timeout: int):
        self.bin, self.timeout = bin, timeout

    def complete(self, prompt: str, json_schema: dict | None = None) -> str:
        if json_schema:
            prompt += "\n\nAnswer with a single JSON object matching this JSON schema:\n" + json.dumps(json_schema)
        with tempfile.TemporaryDirectory() as cwd:
            try:
                p = subprocess.run([self.bin, *ARGS], input=prompt, capture_output=True, text=True,
                                   timeout=self.timeout, cwd=cwd)
            except FileNotFoundError:
                raise LLMError("claude CLI not found: install Claude Code and run 'claude' once to log in")
            except subprocess.TimeoutExpired:
                raise LLMError(f"claude CLI timed out after {self.timeout}s")
        try:
            out = json.loads(p.stdout)
        except json.JSONDecodeError:
            raise LLMError(f"claude CLI failed (exit {p.returncode}): {(p.stderr or p.stdout)[:300]}")
        if out.get("is_error") or p.returncode != 0:
            raise LLMError(f"claude CLI error: {out.get('result') or p.stderr[:300]}")
        return out["result"]

import httpx

from gmaj.llm import LLMError


class OllamaLLM:
    def __init__(self, url: str, model: str, timeout: int):
        self.url, self.model, self.timeout = url.rstrip("/"), model, timeout

    def complete(self, prompt: str, json_schema: dict | None = None) -> str:
        body = {"model": self.model, "prompt": prompt, "stream": False, "think": False,
                "format": json_schema or "json"}
        try:
            r = httpx.post(f"{self.url}/api/generate", json=body, timeout=self.timeout)
            r.raise_for_status()
            return r.json()["response"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise LLMError(f"ollama ({self.model}) failed: {e}") from e

    def is_available(self) -> bool:
        try:
            names = [m["name"] for m in httpx.get(f"{self.url}/api/tags", timeout=3).json()["models"]]
        except (httpx.HTTPError, KeyError, ValueError):
            return False
        return self.model in names or f"{self.model}:latest" in names

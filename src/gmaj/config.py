import os
from pathlib import Path

import platformdirs
import yaml
from pydantic import BaseModel


def data_dir() -> Path:
    d = Path(os.environ.get("GMAJ_DATA_DIR") or platformdirs.user_data_dir("get_me_a_job"))
    d.mkdir(parents=True, exist_ok=True)
    return d


class LLMSettings(BaseModel):
    onboarding: str = "claude_cli"
    scoring: str = "ollama"
    on_demand_scoring: str = "claude_cli"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3.5:9b"
    claude_bin: str = "claude"
    timeout_s: int = 300


class Settings(BaseModel):
    llm: LLMSettings = LLMSettings()
    max_scored_per_run: int = 30
    reliefweb_appname: str | None = None
    port: int = 8765
    user_agent: str = "get_me_a_job/0.1"


def load_settings(dir: Path | None = None) -> Settings:
    path = (dir or data_dir()) / "settings.yaml"
    if not path.exists():
        return Settings()
    return Settings.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def save_settings(s: Settings, dir: Path | None = None) -> None:
    path = (dir or data_dir()) / "settings.yaml"
    path.write_text(yaml.safe_dump(s.model_dump(), sort_keys=False, allow_unicode=True), encoding="utf-8")

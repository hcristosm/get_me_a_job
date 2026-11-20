import shutil

from conftest import EX
from gmaj.cli import main


def test_collect_without_profile_returns_1(data_dir, capsys):
    assert main(["collect"]) == 1
    assert "gmaj init" in capsys.readouterr().out


def test_collect_runs_and_prints_report(data_dir, monkeypatch, capsys, board_client):
    shutil.copy(EX / "profile.example.yaml", data_dir / "profile.yaml")
    shutil.copy(EX / "search.example.yaml", data_dir / "search.yaml")
    monkeypatch.setattr("gmaj.sources.make_client", lambda s: board_client)
    monkeypatch.setattr("gmaj.llm.ollama.OllamaLLM.is_available", lambda self: False)
    assert main(["collect"]) == 0
    out = capsys.readouterr().out
    assert "new" in out and (data_dir / "jobs.sqlite").exists()

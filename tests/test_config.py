import pytest


def test_data_dir_honors_env(data_dir):
    from gmaj.config import data_dir as dd
    assert dd() == data_dir


def test_settings_defaults_when_missing(data_dir):
    from gmaj.config import load_settings
    s = load_settings()
    assert s.llm.scoring == "ollama" and s.llm.ollama_model == "qwen3.5:9b"
    assert s.port == 8765 and s.reliefweb_appname is None
    assert not (data_dir / "settings.yaml").exists()


def test_settings_roundtrip(data_dir):
    from gmaj.config import load_settings, save_settings
    s = load_settings()
    s.llm.ollama_model = "gemma4:12b"
    save_settings(s)
    assert load_settings().llm.ollama_model == "gemma4:12b"


def test_cli_help_exits_zero():
    from gmaj.cli import main
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0

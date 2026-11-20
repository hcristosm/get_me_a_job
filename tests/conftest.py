import pytest


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAJ_DATA_DIR", str(tmp_path))
    return tmp_path

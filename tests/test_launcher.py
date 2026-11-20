import shutil

from fastapi.testclient import TestClient

from conftest import EX
from gmaj.launcher import Activity, should_stop
from gmaj.web.app import create_app


def test_alive_and_bye_endpoints(data_dir):
    shutil.copy(EX / "profile.example.yaml", data_dir / "profile.yaml")
    act = Activity(last_seen=0)
    c = TestClient(create_app(data_dir, activity=act), base_url="http://127.0.0.1:8765")
    assert c.get("/api/alive").json() == {"ok": True} and act.last_seen > 0
    assert c.post("/api/bye", headers={"origin": "http://127.0.0.1:8765"}).status_code == 200
    assert act.bye_at is not None
    assert "/api/alive" in c.get("/jobs?status=new").text  # pages ping


def test_should_stop_after_bye_without_ping():
    act = Activity(last_seen=100)
    act.bye(101)
    assert not should_stop(105, act, collecting=False)
    assert should_stop(110, act, collecting=False)


def test_navigation_ping_cancels_bye():
    act = Activity(last_seen=100)
    act.bye(101)
    act.alive(102)  # next page loaded
    assert not should_stop(150, act, collecting=False)


def test_should_stop_after_timeout():
    act = Activity(last_seen=100)
    assert not should_stop(180, act, collecting=False)
    assert should_stop(191, act, collecting=False)


def test_never_stops_while_collecting():
    act = Activity(last_seen=0)
    act.bye(1)
    assert not should_stop(10_000, act, collecting=True)


def test_open_reuses_running_server(monkeypatch):
    from gmaj import launcher
    opened = []
    monkeypatch.setattr(launcher, "already_running", lambda port: True)
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: opened.append(url))
    monkeypatch.setattr(launcher.uvicorn, "Server", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no server")))
    assert launcher.open_app(8765) == 0
    assert opened == ["http://127.0.0.1:8765"]


def test_already_running_false_on_closed_port():
    from gmaj.launcher import already_running
    assert already_running(9) is False


def test_watchdog_stops_server(tmp_path):
    from gmaj.launcher import watch

    class FakeServer:
        should_exit = False
    srv = FakeServer()
    watch(srv, Activity(last_seen=-1000), tmp_path / "collect.lock", interval=0.01)
    assert srv.should_exit


def test_desktop_entry_content():
    from gmaj.launcher import desktop_entry
    e = desktop_entry("/home/x/my apps/gmaj")
    assert 'Exec="/home/x/my apps/gmaj" open' in e and "Terminal=false" in e
    assert e.startswith("[Desktop Entry]") and "Type=Application" in e and "Name=get_me_a_job" in e


def test_install_launcher_writes_files(tmp_path, monkeypatch):
    from gmaj import launcher
    monkeypatch.setattr(launcher.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(launcher.subprocess, "run", lambda *a, **k: None)
    (tmp_path / "Desktop").mkdir()
    paths = launcher.install_launcher(desktop=True)
    menu = tmp_path / ".local/share/applications/get_me_a_job.desktop"
    assert menu in paths and menu.exists() and (tmp_path / "Desktop/get_me_a_job.desktop").exists()
    assert (tmp_path / "Desktop/get_me_a_job.desktop").stat().st_mode & 0o100

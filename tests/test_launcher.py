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

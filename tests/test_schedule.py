from gmaj.schedule import install, remove, unit_files


def test_unit_files_content():
    u = unit_files("/opt/venv/bin/gmaj", hour=7)
    assert "ExecStart=/opt/venv/bin/gmaj collect" in u["gmaj-collect.service"]
    assert "Type=oneshot" in u["gmaj-collect.service"]
    t = u["gmaj-collect.timer"]
    assert "OnCalendar=*-*-* 07:00:00" in t and "Persistent=true" in t and "WantedBy=timers.target" in t


def _fake(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("gmaj.schedule.Path.home", lambda: tmp_path)
    monkeypatch.setattr("gmaj.schedule.subprocess.run", lambda args, **kw: calls.append(args))
    return calls


def test_install_writes_and_enables(tmp_path, monkeypatch):
    calls = _fake(monkeypatch, tmp_path)
    install()
    assert (tmp_path / ".config/systemd/user/gmaj-collect.timer").exists()
    assert ["systemctl", "--user", "enable", "--now", "gmaj-collect.timer"] in calls


def test_remove_disables_and_deletes(tmp_path, monkeypatch):
    calls = _fake(monkeypatch, tmp_path)
    install()
    remove()
    assert ["systemctl", "--user", "disable", "--now", "gmaj-collect.timer"] in calls
    assert not (tmp_path / ".config/systemd/user/gmaj-collect.timer").exists()


def test_serve_and_init_never_install_a_timer():
    import inspect
    from gmaj import cli, onboarding
    from gmaj.web import app
    for mod in (onboarding, app):
        assert "schedule" not in inspect.getsource(mod)
    assert "install(" in inspect.getsource(cli)  # only behind the explicit `schedule install` command

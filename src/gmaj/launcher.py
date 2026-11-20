"""One-click mode: open the dashboard, and stop the server once the browser is closed."""
import subprocess
import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import httpx
import uvicorn


@dataclass
class Activity:
    last_seen: float
    bye_at: float | None = None

    def alive(self, now: float | None = None) -> None:
        self.last_seen = now if now is not None else time.monotonic()

    def bye(self, now: float | None = None) -> None:
        self.bye_at = now if now is not None else time.monotonic()


def should_stop(now: float, act: Activity, collecting: bool, timeout: float = 90, grace: float = 8) -> bool:
    """Stop shortly after the last page said bye (unless another page pinged), or after `timeout` of silence."""
    if collecting:
        return False
    if act.bye_at is not None and act.last_seen <= act.bye_at and now - act.bye_at >= grace:
        return True
    return now - act.last_seen >= timeout


def already_running(port: int) -> bool:
    try:
        return httpx.get(f"http://127.0.0.1:{port}/api/alive", timeout=1).json().get("ok") is True
    except (httpx.HTTPError, ValueError, AttributeError):
        return False


def watch(server, act: Activity, lock_path: Path, interval: float = 2) -> None:
    from gmaj.pipeline import is_collecting
    while not server.should_exit:
        if should_stop(time.monotonic(), act, is_collecting(lock_path)):
            server.should_exit = True
            return
        time.sleep(interval)


def open_app(port: int, data: Path | None = None) -> int:
    """Open the dashboard; start a server that stops by itself once no page is open."""
    from gmaj.config import data_dir
    from gmaj.web.app import create_app
    url = f"http://127.0.0.1:{port}"
    if already_running(port):  # second double-click: just show the open app
        webbrowser.open(url)
        return 0
    act = Activity(last_seen=time.monotonic())
    server = uvicorn.Server(uvicorn.Config(create_app(data, activity=act), host="127.0.0.1", port=port,
                                           log_level="warning"))

    def open_when_ready():
        while not server.started and not server.should_exit:
            time.sleep(0.1)
        if server.started:
            webbrowser.open(url)

    threading.Thread(target=watch, args=(server, act, (data or data_dir()) / "collect.lock"), daemon=True).start()
    threading.Thread(target=open_when_ready, daemon=True).start()
    server.run()
    return 0


def desktop_entry(exe: str) -> str:
    return ("[Desktop Entry]\nType=Application\nName=get_me_a_job\n"
            "Comment=Find niche jobs and score your fit\n"
            f'Exec="{exe}" open\nTerminal=false\nIcon=system-search\nCategories=Office;\n')


def install_launcher(desktop: bool = False) -> list[Path]:
    """Linux: add a menu entry (and optionally a desktop icon) that runs `gmaj open`."""
    from gmaj.schedule import gmaj_exe
    entry = desktop_entry(gmaj_exe())
    targets = [Path.home() / ".local/share/applications/get_me_a_job.desktop"]
    if desktop:
        desk = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True)
        targets.append(Path(desk.stdout.strip() if desk and desk.stdout.strip() else Path.home() / "Desktop")
                       / "get_me_a_job.desktop")
    for t in targets:
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(entry)
        t.chmod(0o755)
    if desktop:  # GNOME asks before running untrusted desktop icons; best effort
        subprocess.run(["gio", "set", str(targets[-1]), "metadata::trusted", "true"], capture_output=True)
    return targets

"""Optional, opt-in daily collect via a systemd user timer. Nothing calls this unless the user runs `gmaj schedule install`."""
import shutil
import subprocess
import sys
from pathlib import Path

NAMES = ("gmaj-collect.service", "gmaj-collect.timer")


def unit_files(gmaj_exe: str, hour: int = 8) -> dict[str, str]:
    return {
        "gmaj-collect.service": f"[Unit]\nDescription=get_me_a_job daily collect\n\n"
                                f"[Service]\nType=oneshot\nExecStart={gmaj_exe} collect\n",
        "gmaj-collect.timer": f"[Unit]\nDescription=get_me_a_job daily collect\n\n"
                              f"[Timer]\nOnCalendar=*-*-* {hour:02d}:00:00\nPersistent=true\n\n"
                              f"[Install]\nWantedBy=timers.target\n",
    }


def _dir() -> Path:
    return Path.home() / ".config/systemd/user"


def gmaj_exe() -> str:
    return shutil.which("gmaj") or str(Path(sys.argv[0]).resolve())


def install(hour: int = 8) -> None:
    _dir().mkdir(parents=True, exist_ok=True)
    for name, text in unit_files(gmaj_exe(), hour).items():
        (_dir() / name).write_text(text)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "gmaj-collect.timer"], check=True)


def remove() -> None:
    subprocess.run(["systemctl", "--user", "disable", "--now", "gmaj-collect.timer"], check=False)
    for name in NAMES:
        (_dir() / name).unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)

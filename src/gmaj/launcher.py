"""One-click mode: open the dashboard, and stop the server once the browser is closed."""
import time
from dataclasses import dataclass


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

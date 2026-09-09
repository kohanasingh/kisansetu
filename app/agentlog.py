"""In-memory rolling event log powering the live 'agent activity' feed,
surfaced as a demo control on web/demo.html and on the FPO dashboard.
Not persisted; resets with the process or a demo reset.
"""

from __future__ import annotations

import time
from collections import deque

_events: deque[dict] = deque(maxlen=200)


def log_event(agent: str, summary: str, payload: dict | list | str | None = None) -> None:
    _events.append({"ts": time.time(), "agent": agent, "summary": summary, "payload": payload})


def recent(limit: int = 50) -> list[dict]:
    return list(_events)[-limit:]


def clear() -> None:
    _events.clear()

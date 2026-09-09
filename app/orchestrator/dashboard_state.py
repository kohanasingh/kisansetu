"""In-memory per-sender dashboard state, read by web/demo.html's FPO
Dashboard column (GET /api/farmer/dashboard). Updated by farmer_router.py
after each real agent response — every field here is copied straight from
an actual identity resolution or agent reply, never fabricated for the UI.
"""

from __future__ import annotations

import time

_state: dict[str, dict] = {}


def update(sender: str, **fields) -> None:
    state = _state.setdefault(sender, {})
    state.update(fields)
    state["updated_at"] = time.time()


def get(sender: str) -> dict:
    return _state.get(sender, {})


def reset(sender: str | None = None) -> None:
    if sender is None:
        _state.clear()
    else:
        _state.pop(sender, None)

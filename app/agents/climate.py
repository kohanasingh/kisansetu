"""Agent — Climate Watch. Checks a real Open-Meteo forecast per FPO region
and raises an alert when it crosses a fixed threshold (heavy rain, storm,
or drought risk) — see services/weather.py for the actual thresholds.

Called two ways:
  - jobs/scheduler.py, on a periodic in-process tick (production behavior).
  - on demand, via the /demo "Simulate Climate Alert" control and the FPO
    dashboard — this doesn't fake an alert, it just runs the same real
    check immediately instead of waiting for the next tick. If conditions
    are calm, it correctly reports no alert rather than inventing one.

New alerts are appended to db/store.py's alert feed, which
agents/farmer_query.py already reads for its grounded facts dict — no
separate wiring needed for a farmer to hear about a new alert.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from app.agentlog import log_event
from app.db import store
from app.services import weather

# An on-demand check (the /demo trigger) can be clicked repeatedly; don't
# log a duplicate alert for the same still-true condition within this
# window. A genuinely new/different condition is never suppressed.
_DEDUP_WINDOW = timedelta(hours=1)


async def check_fpo(fpo: dict) -> dict | None:
    forecast = await weather.get_forecast(fpo["lat"], fpo["lon"])
    if forecast is None:
        log_event("climate", f"forecast fetch failed for {fpo['name']}; skipping this tick")
        return None

    condition = weather.evaluate_alert(forecast)
    if condition is None:
        log_event("climate", f"checked {fpo['name']} — no active weather risk")
        return None

    last = store.recent_alerts(fpo["id"], limit=1)
    if last and last[0]["kind"] == condition["kind"]:
        last_ts = datetime.fromisoformat(last[0]["created_at"])
        if datetime.now(timezone.utc) - last_ts < _DEDUP_WINDOW:
            log_event("climate", f"{condition['kind']} still active for {fpo['name']} — not re-logging")
            return None

    alert = {
        "id": f"alert_{uuid.uuid4().hex[:8]}",
        "fpo_id": fpo["id"],
        "kind": condition["kind"],
        "severity": condition["severity"],
        "message": condition["message"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    store.add_alert(alert)
    log_event("climate", f"{condition['kind']} alert raised for {fpo['name']}", alert)
    return alert


async def check_all_fpos() -> list[dict]:
    # Each FPO's check is an independent Open-Meteo call — run them
    # concurrently rather than one at a time. Safe: check_fpo's only
    # shared-state writes (store.add_alert) are plain synchronous list
    # appends with no `await` inside them, so there's no interleaving
    # risk under asyncio's cooperative model even run concurrently.
    results = await asyncio.gather(*(check_fpo(fpo) for fpo in store.list_fpos()))
    return [alert for alert in results if alert]

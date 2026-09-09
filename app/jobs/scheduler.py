"""Periodic in-process climate check — an asyncio background task started
at app startup, no external cron/broker (consistent with jobs/queue.py).
Ticks agents/climate.py against every seeded FPO on a fixed interval.

The /demo "Simulate Climate Alert" control and the FPO dashboard don't wait
for this — they call agents/climate.check_fpo()/check_all_fpos() directly
for an on-demand real check. This loop exists only so a long-running demo
process eventually raises alerts on its own, the way production would.
"""

from __future__ import annotations

import asyncio
import logging

from app.agents import climate

logger = logging.getLogger("kisansetu.scheduler")

CHECK_INTERVAL_SECONDS = 6 * 60 * 60  # twice a day — Open-Meteo forecasts don't change faster than this

_task: asyncio.Task | None = None


async def _loop() -> None:
    while True:
        try:
            await climate.check_all_fpos()
        except Exception:  # noqa: BLE001 — one bad tick must not kill the scheduler
            logger.exception("climate scheduler tick failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def start() -> None:
    global _task
    if _task is None:
        _task = asyncio.create_task(_loop(), name="climate_scheduler")
        logger.info("climate scheduler started (every %ds)", CHECK_INTERVAL_SECONDS)


def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        _task = None

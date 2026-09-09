"""In-process fire-and-forget async job queue — asyncio.create_task with
error logging, no external broker.

Used for background ingestion parsing, advisory generation, and anything
that must continue after a request returns. Note this is why Cloud Run needs
--no-cpu-throttling (see deploy/cloud_run.md).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine

logger = logging.getLogger("kisansetu.jobs")

_tasks: set[asyncio.Task] = set()


def enqueue(coro: Coroutine, *, name: str = "job") -> None:
    """Fire-and-forget with error logging. Never lets an exception vanish."""

    async def runner():
        try:
            await coro
        except Exception:  # noqa: BLE001 — job errors must be visible, not fatal
            logger.exception("background job %s failed", name)

    task = asyncio.create_task(runner(), name=name)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

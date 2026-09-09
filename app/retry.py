"""Shared exponential-backoff retry helper. Used by app/llm.py (OpenAI +
Gemini calls), app/services/weather.py (Open-Meteo), and
app/transports/whatsapp_cloud.py (Meta Graph API) — every network call in
this codebase retries the same way instead of each module reimplementing
the loop.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger("kisansetu.retry")


async def with_retry(coro_factory: Callable[[], Awaitable], *, what: str,
                      exceptions: tuple[type[Exception], ...], error_cls: type[Exception],
                      attempts: int = 3, base_delay: float = 1.0):
    """Calls coro_factory() up to `attempts` times with exponential backoff
    (base_delay, base_delay*2, ...) on any of `exceptions`. Raises
    `error_cls(f"{what} failed after retries")` once attempts are exhausted."""
    delay = base_delay
    for attempt in range(attempts):
        try:
            return await coro_factory()
        except exceptions as e:
            logger.warning("%s failed (attempt %d/%d): %s", what, attempt + 1, attempts, e)
            if attempt == attempts - 1:
                raise error_cls(f"{what} failed after retries") from e
            await asyncio.sleep(delay)
            delay *= 2

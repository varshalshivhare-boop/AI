"""Reconnect loop with backoff. Failures are logged and metered. The final failure is re-raised."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from ..backoff import Backoff
from ..metrics import MarketDataMetrics

logger = logging.getLogger("qm_md.reconnect")


async def run_with_reconnect(
    session: Callable[[], Awaitable[None]],
    *,
    backoff: Backoff,
    metrics: MarketDataMetrics,
    max_attempts: int | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Run session() until it returns normally. On failure, back off and retry.

    Each failure increments reconnects_total. Once max_attempts consecutive failures occur,
    the last exception is re-raised. A clean return resets the backoff.
    """
    failures = 0
    while True:
        try:
            await session()
            backoff.reset()
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failures += 1
            metrics.reconnects.inc()
            if max_attempts is not None and failures >= max_attempts:
                logger.error(
                    "reconnect budget exhausted",
                    exc_info=True,
                    extra={"event": "reconnect_exhausted", "attempts": failures},
                )
                raise
            delay = backoff.next_delay()
            logger.warning(
                "session failed, reconnecting",
                extra={
                    "event": "reconnect",
                    "attempt": failures,
                    "delay_seconds": round(delay, 3),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            await sleep(delay)

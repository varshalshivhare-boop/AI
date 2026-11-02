"""Redis Streams publisher. Publishing is non-fatal: a failed write is logged and metered.

Durable storage (the candles table) is the system of record. Streams are the live delivery path.
A candle that failed to publish is still persisted and can be replayed from the database.
Only redis/socket errors are caught here. Any other exception is a bug and propagates.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from redis.exceptions import RedisError

from .contracts import candle_payload, tick_payload
from .metrics import MarketDataMetrics
from .models import Candle, Tick

logger = logging.getLogger("qm_md.publish")

TICKS_STREAM = "ticks.normalized"
HEALTH_STREAM = "provider.health"
OPEN_CANDLE_MAXLEN = 1000


def open_candle_stream(timeframe: str) -> str:
    return f"candles.open.{timeframe}"


def candle_stream(timeframe: str) -> str:
    return f"candles.closed.{timeframe}"


class RedisPublisher:
    def __init__(
        self,
        client: Any,  # redis.asyncio.Redis; typed loosely to keep stubs out of the hot path
        metrics: MarketDataMetrics,
        *,
        ticks_maxlen: int = 100_000,
        candles_maxlen: int = 10_000,
        health_maxlen: int = 5_000,
    ) -> None:
        self._client = client
        self._metrics = metrics
        self._maxlen = {
            TICKS_STREAM: ticks_maxlen,
            HEALTH_STREAM: health_maxlen,
        }
        self._candles_maxlen = candles_maxlen

    async def _xadd(self, stream: str, payload: dict[str, Any], maxlen: int) -> bool:
        try:
            await self._client.xadd(
                stream,
                {"payload": json.dumps(payload, separators=(",", ":"))},
                maxlen=maxlen,
                approximate=True,
            )
        except (RedisError, OSError) as exc:
            self._metrics.redis_publish_errors.labels(stream=stream).inc()
            logger.error(
                "redis publish failed",
                exc_info=True,
                extra={"event": "redis_publish_error", "stream": stream,
                       "error_type": type(exc).__name__},
            )
            return False
        return True

    async def publish_tick(self, tick: Tick) -> bool:
        return await self._xadd(TICKS_STREAM, tick_payload(tick), self._maxlen[TICKS_STREAM])

    async def publish_candle(self, candle: Candle) -> bool:
        return await self._xadd(
            candle_stream(candle.timeframe.value), candle_payload(candle), self._candles_maxlen
        )

    async def publish_open_candle(self, candle: Candle) -> bool:
        """Live-view stream. Never used for persistence; consumers must treat it as provisional."""
        if candle.is_final:
            raise ValueError("publish_open_candle received a final candle")
        return await self._xadd(
            open_candle_stream(candle.timeframe.value),
            candle_payload(candle),
            OPEN_CANDLE_MAXLEN,
        )

    async def publish_health(self, payload: dict[str, Any]) -> bool:
        return await self._xadd(HEALTH_STREAM, payload, self._maxlen[HEALTH_STREAM])


class OpenCandleThrottle:
    """Allows at most one open-candle publish per (symbol, timeframe, bar) per interval."""

    def __init__(self, interval: timedelta) -> None:
        if interval <= timedelta(0):
            raise ValueError("interval must be positive")
        self._interval = interval
        self._last: dict[tuple[str, str, datetime], datetime] = {}

    def allow(self, candle: Candle, now: datetime) -> bool:
        key = (candle.symbol, candle.timeframe.value, candle.bar_start_ts)
        last = self._last.get(key)
        if last is not None and now - last < self._interval:
            return False
        self._last[key] = now
        if len(self._last) > 10_000:
            cutoff = now - timedelta(days=1)
            self._last = {k: v for k, v in self._last.items() if v >= cutoff}
        return True

"""Redis Streams publisher. Publishing is non-fatal: a failed write is logged and metered.

Durable storage (the candles table) is the system of record. Streams are the live delivery path.
A candle that failed to publish is still persisted and can be replayed from the database.
Only redis/socket errors are caught here. Any other exception is a bug and propagates.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.exceptions import RedisError

from .contracts import candle_payload, tick_payload
from .metrics import MarketDataMetrics
from .models import Candle, Tick

logger = logging.getLogger("qm_md.publish")

TICKS_STREAM = "ticks.normalized"
HEALTH_STREAM = "provider.health"


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

    async def publish_health(self, payload: dict[str, Any]) -> bool:
        return await self._xadd(HEALTH_STREAM, payload, self._maxlen[HEALTH_STREAM])

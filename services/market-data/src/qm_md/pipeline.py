"""Pipeline orchestration: provider -> normalize -> dedupe -> candles -> store -> publish.

Ordering matters. Candles are written to the store before they are published. A store failure
is fatal (StorageError). A publish failure is not fatal.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .candles import CandleBuilder
from .dedupe import LruDeduper
from .errors import StorageError
from .health import ProviderHealthTracker
from .metrics import MarketDataMetrics
from .models import Candle, Gap, ProviderState, RawTick, Rejection, RejectReason
from .normalize import TickNormalizer
from .providers.base import MarketDataProvider
from .publish import RedisPublisher
from .store import CandleStore

logger = logging.getLogger("qm_md.pipeline")


@dataclass
class RunSummary:
    ticks_received: int = 0
    ticks_accepted: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    candles_emitted: dict[str, int] = field(default_factory=dict)
    gaps: int = 0
    publish_failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticks_received": self.ticks_received,
            "ticks_accepted": self.ticks_accepted,
            "rejected": dict(sorted(self.rejected.items())),
            "candles_emitted": dict(sorted(self.candles_emitted.items())),
            "gaps": self.gaps,
            "publish_failures": self.publish_failures,
        }


class MarketDataPipeline:
    def __init__(
        self,
        *,
        provider: MarketDataProvider,
        normalizer: TickNormalizer,
        deduper: LruDeduper,
        builders: Sequence[CandleBuilder],
        store: CandleStore,
        metrics: MarketDataMetrics,
        clock: Callable[[], datetime],
        publisher: RedisPublisher | None = None,
        publish_ticks: bool = True,
    ) -> None:
        self._provider = provider
        self._normalizer = normalizer
        self._deduper = deduper
        self._builders = list(builders)
        self._store = store
        self._metrics = metrics
        self._clock = clock
        self._publisher = publisher
        self._publish_ticks = publish_ticks
        self._health = ProviderHealthTracker(provider.name, provider.data_mode)
        self._summary = RunSummary()

    async def run(self) -> RunSummary:
        logger.info("pipeline starting", extra={"event": "pipeline_start",
                                                "provider": self._provider.name})
        await self._provider.connect()
        try:
            await self._set_health(ProviderState.CONNECTED, "CONNECTED")
            async for raw in self._provider.stream():
                await self._handle(raw)
            for builder in self._builders:
                await self._emit_candles(builder.flush_all())
            await self._set_health(ProviderState.STOPPED, "STREAM_END")
        except Exception as exc:
            logger.error("pipeline failed", exc_info=True,
                         extra={"event": "pipeline_error", "error_type": type(exc).__name__})
            await self._set_health(ProviderState.ERROR, type(exc).__name__)
            raise
        finally:
            await self._safe_disconnect()
        logger.info("pipeline finished", extra={"event": "pipeline_end",
                                                "summary": self._summary.to_dict()})
        return self._summary

    @property
    def summary(self) -> RunSummary:
        return self._summary

    async def _handle(self, raw: RawTick) -> None:
        self._summary.ticks_received += 1
        self._metrics.ticks_received.inc()

        normalized = self._normalizer.normalize(raw)
        if isinstance(normalized, Rejection):
            self._reject([normalized])
            return
        tick = normalized

        if self._deduper.check_and_add(tick):
            self._reject([Rejection(reason=RejectReason.DUPLICATE, symbol=tick.symbol,
                                    detail="duplicate provider key")])
            return

        self._summary.ticks_accepted += 1
        self._metrics.last_tick_age.set(
            max(0.0, (self._clock() - tick.ingest_ts).total_seconds())
        )
        if self._publish_ticks and self._publisher is not None and not await (
            self._publisher.publish_tick(tick)
        ):
            self._summary.publish_failures += 1

        rejections: dict[RejectReason, Rejection] = {}
        for builder in self._builders:
            result = builder.add(tick)
            if result.rejection is not None:
                rejections.setdefault(result.rejection.reason, result.rejection)
            for gap in result.gaps:
                self._record_gap(gap)
            await self._emit_candles(result.closed)
        if rejections:
            self._reject(list(rejections.values()))

    def _reject(self, rejections: list[Rejection]) -> None:
        for rejection in rejections:
            reason = rejection.reason.value
            self._summary.rejected[reason] = self._summary.rejected.get(reason, 0) + 1
            self._metrics.ticks_rejected.labels(reason=reason).inc()
            logger.warning(
                "tick rejected",
                extra={"event": "tick_rejected", "reason": reason,
                       "symbol": rejection.symbol, "detail": rejection.detail},
            )

    def _record_gap(self, gap: Gap) -> None:
        self._summary.gaps += 1
        self._metrics.candle_gaps.labels(tf=gap.timeframe.value).inc()
        logger.warning(
            "intraday bar has no ticks; no candle emitted",
            extra={"event": "candle_gap", "symbol": gap.symbol, "tf": gap.timeframe.value,
                   "missing_start": gap.missing_start.isoformat()},
        )

    async def _emit_candles(self, candles: list[Candle]) -> None:
        if not candles:
            return
        try:
            await self._store.upsert_many(candles)
        except StorageError:
            self._metrics.store_errors.inc()
            raise
        for candle in candles:
            tf = candle.timeframe.value
            self._summary.candles_emitted[tf] = self._summary.candles_emitted.get(tf, 0) + 1
            self._metrics.candles_emitted.labels(tf=tf).inc()
            if self._publisher is not None and not await self._publisher.publish_candle(candle):
                self._summary.publish_failures += 1

    async def _set_health(self, state: ProviderState, reason: str) -> None:
        payload = self._health.transition(state, reason, now=self._clock())
        if payload is not None and self._publisher is not None and not await (
            self._publisher.publish_health(payload)
        ):
            self._summary.publish_failures += 1

    async def _safe_disconnect(self) -> None:
        try:
            await self._provider.disconnect()
        except Exception:
            # Logged with traceback, not re-raised, so it cannot mask the original failure.
            logger.error("provider disconnect failed", exc_info=True,
                         extra={"event": "disconnect_error"})

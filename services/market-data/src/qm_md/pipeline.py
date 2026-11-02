"""Pipeline orchestration: provider -> normalize -> dedupe -> ticks -> candles -> store -> publish.

Ordering matters. Candles are written to the store before they are published. A store failure
is fatal (StorageError). A publish failure is not fatal.

Liveness: when configured, a watchdog runs beside the consumer. During the regular session it
publishes DEGRADED/STALE_DATA once when no tick has arrived for the threshold, and CONNECTED once
when data resumes. Outside the session it publishes nothing.

Stop: request_stop() ends consumption at the next opportunity, even if the provider is silent.
Everything already accepted is flushed (open candles closed, tick buffer written), and STOPPED
is published before run() returns normally.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .candles import CandleBuilder
from .dedupe import LruDeduper
from .errors import StorageError
from .health import ProviderHealthTracker
from .metrics import MarketDataMetrics
from .models import Candle, Gap, ProviderState, RawTick, Rejection, RejectReason
from .normalize import TickNormalizer
from .providers.base import MarketDataProvider
from .publish import OpenCandleThrottle, RedisPublisher
from .stale import StaleMonitor
from .store import CandleStore
from .ticks import TickWriter

logger = logging.getLogger("qm_md.pipeline")


@dataclass(frozen=True, slots=True)
class LivenessConfig:
    threshold: timedelta
    in_regular_session: Callable[[datetime], bool]
    check_interval_seconds: float = 1.0


@dataclass
class RunSummary:
    ticks_received: int = 0
    ticks_accepted: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    candles_emitted: dict[str, int] = field(default_factory=dict)
    gaps: int = 0
    publish_failures: int = 0
    stopped_early: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticks_received": self.ticks_received,
            "ticks_accepted": self.ticks_accepted,
            "rejected": dict(sorted(self.rejected.items())),
            "candles_emitted": dict(sorted(self.candles_emitted.items())),
            "gaps": self.gaps,
            "publish_failures": self.publish_failures,
            "stopped_early": self.stopped_early,
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
        tick_writer: TickWriter | None = None,
        open_candle_throttle: OpenCandleThrottle | None = None,
        liveness: LivenessConfig | None = None,
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
        self._tick_writer = tick_writer
        self._open_throttle = open_candle_throttle
        self._liveness = liveness
        self._stop_event = asyncio.Event()
        self._last_seen: datetime | None = None
        self._connected_at: datetime | None = None
        self._stale = (StaleMonitor(liveness.threshold) if liveness is not None else None)
        self._health = ProviderHealthTracker(provider.name, provider.data_mode)
        self._summary = RunSummary()

    @property
    def summary(self) -> RunSummary:
        return self._summary

    def request_stop(self) -> None:
        """Ask the run to stop. Safe to call from a signal handler or another task."""
        self._stop_event.set()

    async def run(self) -> RunSummary:
        logger.info("pipeline starting", extra={"event": "pipeline_start",
                                                "provider": self._provider.name})
        await self._provider.connect()
        watchdog: asyncio.Task[None] | None = None
        try:
            self._connected_at = self._clock()
            await self._set_health(ProviderState.CONNECTED, "CONNECTED")
            if self._liveness is not None:
                watchdog = asyncio.create_task(self._watch())
            await self._consume()
            if self._stop_event.is_set():
                self._summary.stopped_early = True
            for builder in self._builders:
                await self._emit_candles(builder.flush_all())
            if self._tick_writer is not None:
                await self._tick_writer.close()
            await self._set_health(
                ProviderState.STOPPED,
                "STOP_REQUESTED" if self._stop_event.is_set() else "STREAM_END",
            )
        except Exception as exc:
            logger.error("pipeline failed", exc_info=True,
                         extra={"event": "pipeline_error", "error_type": type(exc).__name__})
            await self._set_health(ProviderState.ERROR, type(exc).__name__)
            raise
        finally:
            if watchdog is not None:
                watchdog.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await watchdog
            await self._safe_disconnect()
        logger.info("pipeline finished", extra={"event": "pipeline_end",
                                                "summary": self._summary.to_dict()})
        return self._summary

    async def _consume(self) -> None:
        """Pull ticks until the stream ends or a stop is requested.

        The stop event is raced against each pull, so a silent provider cannot block shutdown.
        A tick that has already been pulled is always handled in full before the loop exits.
        """
        iterator: AsyncIterator[RawTick] = self._provider.stream()
        while not self._stop_event.is_set():
            pull = asyncio.ensure_future(iterator.__anext__())
            stop = asyncio.ensure_future(self._stop_event.wait())
            done, _ = await asyncio.wait({pull, stop}, return_when=asyncio.FIRST_COMPLETED)
            stop.cancel()
            if pull not in done:
                pull.cancel()
                with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
                    await pull
                break
            try:
                raw = pull.result()
            except StopAsyncIteration:
                break
            await self._handle(raw)

    async def _handle(self, raw: RawTick) -> None:
        self._summary.ticks_received += 1
        self._metrics.ticks_received.inc()
        now = self._clock()

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
        self._last_seen = now
        self._metrics.last_tick_age.set(max(0.0, (now - tick.ingest_ts).total_seconds()))
        await self._maybe_recover(now)

        if self._publish_ticks and self._publisher is not None and not await (
            self._publisher.publish_tick(tick)
        ):
            self._summary.publish_failures += 1
        if self._tick_writer is not None:
            await self._tick_writer.add(tick)

        rejections: dict[RejectReason, Rejection] = {}
        for builder in self._builders:
            result = builder.add(tick)
            if result.rejection is not None:
                rejections.setdefault(result.rejection.reason, result.rejection)
            for gap in result.gaps:
                self._record_gap(gap)
            await self._emit_candles(result.closed)
            await self._publish_open(builder, tick.symbol, now)
        if rejections:
            self._reject(list(rejections.values()))

    async def _publish_open(self, builder: CandleBuilder, symbol: str, now: datetime) -> None:
        if self._publisher is None or self._open_throttle is None:
            return
        for candle in builder.open_candles(symbol):
            if not self._open_throttle.allow(candle, now):
                continue
            if not await self._publisher.publish_open_candle(candle):
                self._summary.publish_failures += 1

    # liveness

    async def _watch(self) -> None:
        assert self._liveness is not None
        while True:
            await asyncio.sleep(self._liveness.check_interval_seconds)
            await self._check_liveness()

    async def _check_liveness(self) -> None:
        if self._liveness is None or self._stale is None:
            return
        now = self._clock()
        if not self._liveness.in_regular_session(now):
            return
        reference = self._last_seen or self._connected_at
        if self._health.state is ProviderState.CONNECTED and self._stale.is_stale(
            now=now, reference_ts=reference, in_regular_session=True
        ):
            silent = (now - reference).total_seconds() if reference is not None else None
            logger.warning("no ticks within threshold",
                           extra={"event": "stale_data", "seconds_silent": silent})
            await self._set_health(ProviderState.DEGRADED, "STALE_DATA", seconds_silent=silent)

    async def _maybe_recover(self, now: datetime) -> None:
        if self._liveness is None or self._health.state is not ProviderState.DEGRADED:
            return
        if self._liveness.in_regular_session(now):
            await self._set_health(ProviderState.CONNECTED, "DATA_RESUMED")

    # helpers

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

    async def _set_health(self, state: ProviderState, reason: str,
                          seconds_silent: float | None = None) -> None:
        payload = self._health.transition(
            state, reason, now=self._clock(), seconds_since_last_tick=seconds_silent,
        )
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

"""Milestone 2.5: a stop request mid-run flushes everything and returns normally."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from qm_md.candles import CandleBuilder
from qm_md.dedupe import LruDeduper
from qm_md.metrics import MarketDataMetrics
from qm_md.models import ProviderState, RawTick, Timeframe
from qm_md.normalize import TickNormalizer
from qm_md.pipeline import MarketDataPipeline
from qm_md.providers.replay import ReplayProvider
from qm_md.store import InMemoryCandleStore
from support import DAY, FIXTURES, calendar
from phase2_support import RecordingPublisher


class StopAfter(ReplayProvider):
    def __init__(self, n: int, pipeline_ref: list[MarketDataPipeline], **kw: object) -> None:
        super().__init__(FIXTURES, ("RELIANCE",), session_dates=(DAY,), **kw)  # type: ignore[arg-type]
        self._n = n
        self._ref = pipeline_ref

    async def stream(self) -> AsyncIterator[RawTick]:  # type: ignore[override]
        count = 0
        async for tick in super().stream():
            count += 1
            if count == self._n:
                self._ref[0].request_stop()
            yield tick


async def test_stop_mid_replay_flushes_candles_and_publishes_stopped() -> None:
    ref: list[MarketDataPipeline] = []
    provider = StopAfter(300, ref, clock=lambda: datetime.now(UTC))
    store = InMemoryCandleStore()
    publisher = RecordingPublisher()
    cal = calendar()
    pipeline = MarketDataPipeline(
        provider=provider, normalizer=TickNormalizer(["RELIANCE"]),
        deduper=LruDeduper(10_000),
        builders=[CandleBuilder(Timeframe.M1, cal), CandleBuilder(Timeframe.D1, cal)],
        store=store, metrics=MarketDataMetrics(), clock=lambda: datetime.now(UTC),
        publisher=publisher,  # type: ignore[arg-type]
    )
    ref.append(pipeline)

    summary = await pipeline.run()  # must return, not raise

    assert summary.stopped_early is True
    assert summary.ticks_received <= 301
    # Every candle that was emitted is persisted, including the partial bar flushed at stop.
    emitted = sum(summary.candles_emitted.values())
    assert len(store.rows) == emitted and emitted > 0  # type: ignore[attr-defined]
    last = publisher.health[-1]
    assert last["state"] == ProviderState.STOPPED.value
    assert last["reason_code"] == "STOP_REQUESTED"


async def test_stop_while_provider_is_silent_does_not_hang() -> None:
    import asyncio

    class Silent(ReplayProvider):
        async def stream(self) -> AsyncIterator[RawTick]:  # type: ignore[override]
            yield (await super().stream().__anext__())
            await asyncio.sleep(3600)  # provider goes quiet forever
            yield  # pragma: no cover

    ref: list[MarketDataPipeline] = []
    provider = Silent(FIXTURES, ("RELIANCE",), session_dates=(DAY,))
    cal = calendar()
    pipeline = MarketDataPipeline(
        provider=provider, normalizer=TickNormalizer(["RELIANCE"]),
        deduper=LruDeduper(100), builders=[CandleBuilder(Timeframe.M1, cal)],
        store=InMemoryCandleStore(), metrics=MarketDataMetrics(),
        clock=lambda: datetime.now(UTC),
    )
    ref.append(pipeline)
    asyncio.get_running_loop().call_later(0.2, pipeline.request_stop)
    summary = await asyncio.wait_for(pipeline.run(), timeout=5)
    assert summary.stopped_early is True

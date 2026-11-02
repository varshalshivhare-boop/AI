"""Helpers for Phase 2 tests. Test-only."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from qm_md.models import DataMode, ProviderState, RawTick
from qm_md.providers.base import MarketDataProvider


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


class ScriptedLiveProvider(MarketDataProvider):
    """A live-looking provider driven by a script.

    ("tick", None)    emit one tick stamped with the fake clock
    ("silence", secs) advance the fake clock and hold the stream open long enough for watchdogs
    """

    name = "SCRIPTED_LIVE"
    data_mode = DataMode.LIVE

    def __init__(self, clock: FakeClock, script: list[tuple[str, float | None]],
                 *, real_hold_seconds: float = 0.25) -> None:
        self._clock = clock
        self._script = script
        self._hold = real_hold_seconds
        self._state = ProviderState.DISCONNECTED
        self._seq = 0
        self.on_tick_yielded: list[object] = []

    async def connect(self) -> None:
        self._state = ProviderState.CONNECTED

    async def disconnect(self) -> None:
        self._state = ProviderState.STOPPED

    async def subscribe(self, symbols) -> None:  # type: ignore[no-untyped-def]
        return None

    async def unsubscribe(self, symbols) -> None:  # type: ignore[no-untyped-def]
        return None

    def health(self) -> ProviderState:
        return self._state

    async def stream(self) -> AsyncIterator[RawTick]:  # type: ignore[override]
        import asyncio

        for kind, value in self._script:
            if kind == "silence":
                self._clock.advance(value or 0.0)
                await asyncio.sleep(self._hold)
                continue
            self._seq += 1
            now = self._clock()
            yield RawTick(symbol="RELIANCE", exchange="NSE", price="100", quantity=1,
                          provider_ts=now, ingest_ts=now, provider="SCRIPTED_LIVE",
                          data_mode=DataMode.LIVE, provider_sequence=self._seq)
            for hook in self.on_tick_yielded:
                hook()


class RecordingPublisher:
    def __init__(self) -> None:
        self.health: list[dict[str, object]] = []
        self.open_candles: list[dict[str, object]] = []
        self.closed_candles: list[object] = []
        self.ticks = 0

    async def publish_tick(self, tick) -> bool:  # type: ignore[no-untyped-def]
        self.ticks += 1
        return True

    async def publish_candle(self, candle) -> bool:  # type: ignore[no-untyped-def]
        self.closed_candles.append(candle)
        return True

    async def publish_open_candle(self, candle) -> bool:  # type: ignore[no-untyped-def]
        self.open_candles.append({"is_final": candle.is_final, "key": (
            candle.symbol, candle.timeframe.value, candle.bar_start_ts), "candle": candle})
        return True

    async def publish_health(self, payload) -> bool:  # type: ignore[no-untyped-def]
        self.health.append(payload)
        return True


def utc_ist(hour: int, minute: int, second: int = 0) -> datetime:
    from qm_md.sessions import IST

    return datetime(2026, 10, 19, hour, minute, second, tzinfo=IST).astimezone(UTC)

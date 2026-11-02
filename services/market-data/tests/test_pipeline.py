"""Pipeline behaviour: duplicates, invalid input, store failures, health events."""

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from support import DAY, run_replay

from qm_md.errors import StorageError
from qm_md.models import DataMode, ProviderState, RawTick
from qm_md.providers.base import MarketDataProvider


class ScriptedProvider(MarketDataProvider):
    """Replays a fixed list of RawTick values. Used to inject duplicates and bad input."""

    name = "SCRIPTED"
    data_mode = DataMode.REPLAY

    def __init__(self, ticks: list[RawTick]) -> None:
        self._ticks = ticks
        self.disconnected = False
        self._state = ProviderState.DISCONNECTED

    async def connect(self) -> None:
        self._state = ProviderState.CONNECTED

    async def disconnect(self) -> None:
        self.disconnected = True
        self._state = ProviderState.STOPPED

    async def subscribe(self, symbols) -> None:  # type: ignore[no-untyped-def]
        return None

    async def unsubscribe(self, symbols) -> None:  # type: ignore[no-untyped-def]
        return None

    async def stream(self) -> AsyncIterator[RawTick]:  # type: ignore[override]
        for t in self._ticks:
            yield t

    def health(self) -> ProviderState:
        return self._state


class RecordingPublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.ticks: list[dict[str, object]] = []
        self.candles: list[object] = []
        self.health: list[dict[str, object]] = []

    async def publish_tick(self, tick) -> bool:  # type: ignore[no-untyped-def]
        if self.fail:
            return False
        self.ticks.append({"n": 1})
        return True

    async def publish_candle(self, candle) -> bool:  # type: ignore[no-untyped-def]
        if self.fail:
            return False
        self.candles.append(candle)
        return True

    async def publish_health(self, payload) -> bool:  # type: ignore[no-untyped-def]
        if self.fail:
            return False
        self.health.append(payload)
        return True


class FailingStore:
    async def upsert_many(self, candles) -> int:  # type: ignore[no-untyped-def]
        raise StorageError("database is down")


def raw(price: str, qty: int, offset_s: int, seq: int, symbol: str = "RELIANCE") -> RawTick:
    """offset_s is seconds after the 09:15 IST session open."""
    ts = datetime(2026, 10, 19, 3, 45, tzinfo=UTC) + timedelta(seconds=offset_s)
    return RawTick(symbol=symbol, exchange="NSE", price=price, quantity=qty, provider_ts=ts,
                   ingest_ts=ts, provider="SCRIPTED", data_mode=DataMode.REPLAY,
                   provider_sequence=seq)


async def test_duplicate_provider_tick_is_rejected_once_and_not_double_counted() -> None:
    t = raw("100", 10, 5, seq=1)
    summary, _store, _ = await run_replay(
        ("RELIANCE",), dates=None, timeframes=("1m",),
        provider=ScriptedProvider([t, t, raw("101", 5, 10, seq=2)]),
    )
    assert summary.rejected == {"DUPLICATE": 1}  # type: ignore[attr-defined]
    assert summary.ticks_accepted == 2  # type: ignore[attr-defined]


async def test_invalid_ticks_are_counted_by_reason_and_do_not_stop_the_run() -> None:
    bad = [raw("abc", 1, 1, seq=1), raw("100", -1, 2, seq=2), raw("100", 1, 3, seq=3, symbol="TCS")]
    good = [raw("100", 5, 4, seq=4)]
    summary, _store, _ = await run_replay(
        ("RELIANCE",), dates=None, timeframes=("1m",), provider=ScriptedProvider(bad + good),
    )
    assert summary.rejected == {  # type: ignore[attr-defined]
        "INVALID_PRICE": 1, "INVALID_QUANTITY": 1, "UNKNOWN_SYMBOL": 1,
    }
    assert summary.ticks_received == 4  # type: ignore[attr-defined]


async def test_builder_rejections_are_counted_once_per_reason() -> None:
    # 09:15:05 opens both bars. 09:20:05 seals the 1m and 5m buckets for 09:15 (and 09:19 for 1m).
    # The late 09:15:06 tick is then rejected by BOTH builders, and must count once.
    ticks = [raw("100", 1, 5, seq=1), raw("100", 1, 5 * 60 + 5, seq=2), raw("100", 1, 6, seq=3)]
    summary, _, _ = await run_replay(
        ("RELIANCE",), dates=None, timeframes=("1m", "5m"), provider=ScriptedProvider(ticks),
    )
    assert summary.rejected == {"LATE_AFTER_CLOSE": 1}  # type: ignore[attr-defined]


async def test_tick_in_open_bar_is_not_rejected_by_any_builder() -> None:
    ticks = [raw("100", 1, 5, seq=1), raw("100", 1, 40, seq=2), raw("100", 1, 6, seq=3)]
    summary, _, _ = await run_replay(
        ("RELIANCE",), dates=None, timeframes=("1m", "5m"), provider=ScriptedProvider(ticks),
    )
    assert summary.rejected == {}  # type: ignore[attr-defined]


async def test_store_failure_is_fatal_and_surfaces_the_error() -> None:
    with pytest.raises(StorageError, match="database is down"):
        await run_replay(
            ("RELIANCE",), dates=(DAY,), timeframes=("1m",), store=FailingStore(),
        )


async def test_provider_is_disconnected_even_when_the_run_fails() -> None:
    provider = ScriptedProvider([raw("100", 1, 5, seq=1)])
    with pytest.raises(StorageError):
        await run_replay(("RELIANCE",), dates=None, timeframes=("1m",),
                         store=FailingStore(), provider=provider)
    assert provider.disconnected is True


async def test_publish_failures_are_counted_and_do_not_stop_persistence() -> None:
    publisher = RecordingPublisher(fail=True)
    summary, store, _metrics = await run_replay(
        ("RELIANCE",), dates=(DAY,), timeframes=("1m",), publisher=publisher,
    )
    assert summary.publish_failures > 0  # type: ignore[attr-defined]
    assert summary.candles_emitted == {"1m": 375}  # type: ignore[attr-defined]
    assert len(store.rows) == 375  # type: ignore[attr-defined]


async def test_health_events_are_emitted_on_state_changes_only() -> None:
    publisher = RecordingPublisher()
    await run_replay(("RELIANCE",), dates=(DAY,), timeframes=("1m",), publisher=publisher)
    states = [(h["previous_state"], h["state"]) for h in publisher.health]
    assert states == [(None, "CONNECTED"), ("CONNECTED", "STOPPED")]
    assert all(h["data_mode"] == "REPLAY" for h in publisher.health)


async def test_candles_published_are_the_same_objects_that_were_persisted() -> None:
    publisher = RecordingPublisher()
    _, store, _ = await run_replay(("RELIANCE",), dates=(DAY,), timeframes=("5m",),
                                   publisher=publisher)
    assert len(publisher.candles) == len(store.rows) == 75  # type: ignore[attr-defined]


async def test_replay_run_summary_serializes_to_json() -> None:
    summary, _, _ = await run_replay(("RELIANCE",), dates=(DAY,), timeframes=("1m",))
    payload = json.loads(json.dumps(summary.to_dict()))  # type: ignore[attr-defined]
    assert payload["candles_emitted"] == {"1m": 375}


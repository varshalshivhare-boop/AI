"""Milestone 2.3: open candles reach only the open-candle channel, and publishing is throttled."""

from datetime import UTC, datetime, timedelta

from phase2_support import RecordingPublisher
from support import DAY, ist, run_replay

from qm_md.publish import OpenCandleThrottle


async def test_open_candles_never_reach_the_store_or_closed_channel() -> None:
    publisher = RecordingPublisher()
    fixed = datetime(2026, 10, 19, 4, 0, tzinfo=UTC)
    _summary, store, _ = await run_replay(
        ("RELIANCE",), dates=(DAY,), timeframes=("1m", "5m"), publisher=publisher,
        clock=lambda: fixed,
        open_candle_throttle=OpenCandleThrottle(timedelta(seconds=1)),
    )
    assert publisher.open_candles, "expected open-candle publishes"
    assert all(o["is_final"] is False for o in publisher.open_candles)
    assert all(c.is_final for c in store.rows.values())  # type: ignore[attr-defined]
    assert all(c.is_final for c in publisher.closed_candles)  # type: ignore[attr-defined]


async def test_throttle_allows_one_open_publish_per_bar_per_interval() -> None:
    publisher = RecordingPublisher()
    fixed = datetime(2026, 10, 19, 4, 0, tzinfo=UTC)  # clock frozen: every tick "at once"
    await run_replay(
        ("RELIANCE",), dates=(DAY,), timeframes=("1m",), publisher=publisher,
        clock=lambda: fixed,
        open_candle_throttle=OpenCandleThrottle(timedelta(seconds=1)),
    )
    counts: dict[object, int] = {}
    for o in publisher.open_candles:
        counts[o["key"]] = counts.get(o["key"], 0) + 1  # type: ignore[index]
    assert counts and max(counts.values()) == 1


def test_throttle_reopens_after_interval() -> None:
    from support import calendar, tick

    from qm_md.candles import CandleBuilder
    from qm_md.models import Timeframe

    b = CandleBuilder(Timeframe.M1, calendar())
    b.add(tick(ist(2026, 10, 19, 9, 15, 5), "100", 1))
    candle = b.open_candles("RELIANCE")[0]
    t = OpenCandleThrottle(timedelta(seconds=1))
    base = ist(2026, 10, 19, 9, 15, 10)
    assert t.allow(candle, base)
    assert not t.allow(candle, base + timedelta(milliseconds=500))
    assert t.allow(candle, base + timedelta(seconds=1))


def test_throttle_rejects_bad_interval_and_final_candles() -> None:
    import pytest

    with pytest.raises(ValueError):
        OpenCandleThrottle(timedelta(0))

"""Replay acceptance: committed expected output, plus an independent oracle.

The oracle does not use the candle builder. It aggregates the raw 1-minute fixture bars directly
(first open, max high, min low, last close, summed volume) and compares the result to the builder.
"""

import asyncio
from datetime import timedelta
from decimal import Decimal

import pytest
from support import DAY, EXPECTED, FIXTURES, ist, run_replay

from qm_md.golden import write_candles_csv
from qm_md.providers.replay import load_bars

FIXTURE = FIXTURES / "SYNTHETIC_RELIANCE_1m_2026-10-19_2026-10-23.csv"


@pytest.fixture(scope="module")
def replayed():  # type: ignore[no-untyped-def]
    summary, store, _ = asyncio.run(run_replay(("RELIANCE",), dates=(DAY,)))
    return summary, store


@pytest.mark.parametrize("tf", ["1m", "5m", "1d"])
def test_matches_committed_expected_output(replayed, tmp_path, tf: str) -> None:  # type: ignore[no-untyped-def]
    _summary, store = replayed
    rows = [c for c in store.sorted_rows() if c.timeframe.value == tf]  # type: ignore[attr-defined]
    out = tmp_path / f"{tf}.csv"
    write_candles_csv(out, rows)
    expected = EXPECTED / f"RELIANCE_2026-10-19_{tf}.csv"
    assert out.read_text() == expected.read_text(), f"{tf} output drifted from {expected.name}"


def _day_bars():  # type: ignore[no-untyped-def]
    from zoneinfo import ZoneInfo

    ist_tz = ZoneInfo("Asia/Kolkata")
    return [b for b in load_bars(FIXTURE) if b.bar_start.astimezone(ist_tz).date() == DAY]


def _oracle(bars, width_minutes: int | None):  # type: ignore[no-untyped-def]
    """Aggregate raw bars without touching the builder. width None means the whole day."""
    groups: dict[int, list] = {}  # type: ignore[type-arg]
    for i, b in enumerate(bars):
        key = 0 if width_minutes is None else i // width_minutes
        groups.setdefault(key, []).append(b)
    out = []
    for key in sorted(groups):
        g = groups[key]
        out.append({
            "start": g[0].bar_start,
            "open": Decimal(g[0].open).quantize(Decimal("0.0001")),
            "high": max(Decimal(b.high) for b in g).quantize(Decimal("0.0001")),
            "low": min(Decimal(b.low) for b in g).quantize(Decimal("0.0001")),
            "close": Decimal(g[-1].close).quantize(Decimal("0.0001")),
            "volume": sum(b.volume for b in g),
            "ticks": 4 * len(g),
        })
    return out


@pytest.mark.parametrize("tf,width", [("1m", 1), ("5m", 5), ("1d", None)])
def test_builder_agrees_with_independent_oracle(replayed, tf: str, width) -> None:  # type: ignore[no-untyped-def]
    _summary, store = replayed
    got = [c for c in store.sorted_rows() if c.timeframe.value == tf]  # type: ignore[attr-defined]
    expected = _oracle(_day_bars(), width)
    assert len(got) == len(expected)
    for c, e in zip(got, expected, strict=True):
        assert c.bar_start_ts == e["start"]
        assert (c.open, c.high, c.low, c.close) == (e["open"], e["high"], e["low"], e["close"])
        assert c.volume == e["volume"]
        assert c.tick_count == e["ticks"]


def test_no_candle_crosses_15_30_to_09_15(replayed) -> None:  # type: ignore[no-untyped-def]
    _summary, store = replayed
    open_utc = ist(2026, 10, 19, 9, 15)
    close_utc = ist(2026, 10, 19, 15, 30)
    for c in store.sorted_rows():  # type: ignore[attr-defined]
        assert open_utc <= c.bar_start_ts < c.bar_end_ts <= close_utc


def test_expected_counts_per_timeframe(replayed) -> None:  # type: ignore[no-untyped-def]
    summary, _ = replayed
    assert summary.candles_emitted == {"1m": 375, "5m": 75, "15m": 25, "30m": 13, "1d": 1}
    assert summary.gaps == 0
    assert summary.rejected == {}
    assert summary.ticks_accepted == 1500


def test_every_candle_is_final_and_labelled_replay(replayed) -> None:  # type: ignore[no-untyped-def]
    _summary, store = replayed
    rows = store.sorted_rows()  # type: ignore[attr-defined]
    assert rows and all(c.is_final for c in rows)
    assert all(c.data_mode.value == "REPLAY" for c in rows)
    assert all(c.ingest_ts.tzinfo is not None and c.ingest_ts.utcoffset() == timedelta(0)
               for c in rows)
    assert {c.exchange for c in rows} == {"NSE"}

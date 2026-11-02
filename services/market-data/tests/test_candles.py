"""Candle builder rules: alignment, session bounds, sealing, gaps, zero volume, out-of-order."""

from datetime import date, timedelta
from decimal import Decimal

from support import calendar, ist, tick

from qm_md.candles import CandleBuilder, bucket_bounds
from qm_md.models import RejectReason, Timeframe
from qm_md.sessions import SessionCalendar

CAL: SessionCalendar = calendar()


def builder(tf: Timeframe) -> CandleBuilder:
    return CandleBuilder(tf, CAL)


def feed(b: CandleBuilder, *ticks: object) -> list:  # type: ignore[type-arg]
    out: list = []  # type: ignore[type-arg]
    for t in ticks:
        out.extend(b.add(t).closed)  # type: ignore[arg-type]
    return out


# --- bucket alignment -----------------------------------------------------------------

def test_buckets_align_to_session_open_not_clock_minutes() -> None:
    session = CAL.session_for_date(DAY)
    start, end = bucket_bounds(session, ist(2026, 10, 19, 9, 17, 30), Timeframe.M5)
    assert start == ist(2026, 10, 19, 9, 15)
    assert end == ist(2026, 10, 19, 9, 20)
    start, end = bucket_bounds(session, ist(2026, 10, 19, 9, 20), Timeframe.M5)
    assert start == ist(2026, 10, 19, 9, 20)


def test_last_thirty_minute_bucket_is_truncated_at_close() -> None:
    session = CAL.session_for_date(DAY)
    start, end = bucket_bounds(session, ist(2026, 10, 19, 15, 20), Timeframe.M30)
    assert start == ist(2026, 10, 19, 15, 15)
    assert end == ist(2026, 10, 19, 15, 30)


def test_daily_bucket_spans_the_whole_session() -> None:
    session = CAL.session_for_date(DAY)
    start, end = bucket_bounds(session, ist(2026, 10, 19, 11, 0), Timeframe.D1)
    assert (start, end) == (session.open_utc, session.close_utc)


DAY = date(2026, 10, 19)


# --- OHLCV correctness ----------------------------------------------------------------

def test_one_minute_candle_ohlcv() -> None:
    b = builder(Timeframe.M1)
    feed(
        b,
        tick(ist(2026, 10, 19, 9, 15, 0), "100.00", 10),
        tick(ist(2026, 10, 19, 9, 15, 20), "102.50", 5),   # high
        tick(ist(2026, 10, 19, 9, 15, 40), "98.75", 7),    # low
    )
    closed = feed(b, tick(ist(2026, 10, 19, 9, 16, 0), "101.00", 1))  # starts next bar
    assert len(closed) == 1
    c = closed[0]
    assert (c.open, c.high, c.low, c.close) == (
        Decimal("100.0000"), Decimal("102.5000"), Decimal("98.7500"), Decimal("98.7500"))
    assert c.volume == 22
    assert c.tick_count == 3
    assert c.is_final is True
    assert c.bar_start_ts == ist(2026, 10, 19, 9, 15)
    assert c.bar_end_ts == ist(2026, 10, 19, 9, 16)


def test_five_minute_candle_aggregates_one_minute_ticks() -> None:
    b = builder(Timeframe.M5)
    ticks = [
        tick(ist(2026, 10, 19, 9, 15, 10), "100", 10),
        tick(ist(2026, 10, 19, 9, 17, 10), "105", 20),
        tick(ist(2026, 10, 19, 9, 19, 59), "99", 30),
    ]
    feed(b, *ticks)
    closed = feed(b, tick(ist(2026, 10, 19, 9, 20, 0), "101", 1))
    assert len(closed) == 1
    assert (closed[0].open, closed[0].high, closed[0].low, closed[0].close) == (
        Decimal("100.0000"), Decimal("105.0000"), Decimal("99.0000"), Decimal("99.0000"))
    assert closed[0].volume == 60


def test_zero_volume_bucket_emits_candle_with_zero_volume() -> None:
    b = builder(Timeframe.M1)
    feed(b, tick(ist(2026, 10, 19, 9, 15, 5), "100", 0))
    closed = feed(b, tick(ist(2026, 10, 19, 9, 16, 5), "100", 0))
    assert len(closed) == 1
    assert closed[0].volume == 0
    assert closed[0].tick_count == 1


def test_open_candles_are_flagged_not_final_and_not_closed() -> None:
    b = builder(Timeframe.M1)
    feed(b, tick(ist(2026, 10, 19, 9, 15, 5), "100", 3))
    live = b.open_candles("RELIANCE")
    assert len(live) == 1
    assert live[0].is_final is False
    assert live[0].volume == 3
    assert b.open_candles("UNKNOWN") == []


def test_flush_all_closes_open_buckets_and_marks_final() -> None:
    b = builder(Timeframe.M15)
    feed(b, tick(ist(2026, 10, 19, 9, 15, 5), "100", 3))
    flushed = b.flush_all()
    assert len(flushed) == 1 and flushed[0].is_final is True
    assert b.open_candles("RELIANCE") == []
    assert b.flush_all() == []


def test_daily_candle_closes_at_session_change() -> None:
    b = builder(Timeframe.D1)
    feed(b, tick(ist(2026, 10, 19, 9, 15, 5), "100", 3),
         tick(ist(2026, 10, 19, 15, 29, 50), "110", 4))
    closed = feed(b, tick(ist(2026, 10, 20, 9, 15, 5), "111", 1))
    assert len(closed) == 1
    c = closed[0]
    assert c.session_date == DAY
    assert c.bar_start_ts == ist(2026, 10, 19, 9, 15)
    assert c.bar_end_ts == ist(2026, 10, 19, 15, 30)
    assert (c.open, c.high, c.low, c.close, c.volume) == (
        Decimal("100.0000"), Decimal("110.0000"), Decimal("100.0000"),
        Decimal("110.0000"), 7)


# --- session boundaries ---------------------------------------------------------------

def test_outside_session_ticks_are_rejected_not_candled() -> None:
    b = builder(Timeframe.M1)
    for at in (ist(2026, 10, 19, 9, 14, 59), ist(2026, 10, 19, 15, 30, 0),
               ist(2026, 10, 24, 10, 0, 0)):
        result = b.add(tick(at))
        assert result.rejection is not None
        assert result.rejection.reason is RejectReason.OUTSIDE_SESSION
        assert result.closed == []


def test_no_candle_spans_the_overnight_gap() -> None:
    b = builder(Timeframe.M30)
    candles = []
    day1 = [ist(2026, 10, 19, 15, 25, 0), ist(2026, 10, 19, 15, 29, 50)]
    day2 = [ist(2026, 10, 20, 9, 15, 0), ist(2026, 10, 20, 9, 20, 0)]
    for at in day1 + day2:
        candles.extend(b.add(tick(at)).closed)
    candles.extend(b.flush_all())
    assert candles, "expected candles"
    for c in candles:
        assert c.bar_start_ts < c.bar_end_ts
        assert c.bar_end_ts - c.bar_start_ts <= timedelta(minutes=30)
        # A candle must not run from one session into the next.
        assert c.bar_start_ts.date() == c.bar_end_ts.date() or c.bar_end_ts.hour < 12
        assert not (c.bar_start_ts <= ist(2026, 10, 19, 15, 30) < c.bar_end_ts)


def test_session_bounds_hold_across_a_full_day_for_all_timeframes() -> None:
    from support import FIXTURES

    from qm_md.providers.replay import load_bars

    bars = load_bars(FIXTURES / "SYNTHETIC_RELIANCE_1m_2026-10-19_2026-10-23.csv")
    day_bars = [x for x in bars if x.bar_start.astimezone().date() == DAY
                or x.bar_start.date() == DAY]
    for tf in Timeframe:
        b = builder(tf)
        out = []
        for bar in day_bars[:375]:
            for offset_s, price in ((0, bar.open), (59, bar.close)):
                out.extend(b.add(tick(bar.bar_start + timedelta(seconds=offset_s),
                                      price, 1)).closed)
        out.extend(b.flush_all())
        assert out
        open_, close_ = CAL.session_for_date(DAY).open_utc, CAL.session_for_date(DAY).close_utc
        for c in out:
            assert open_ <= c.bar_start_ts < c.bar_end_ts <= close_


# --- sealing, late ticks, out-of-order ------------------------------------------------

def test_late_tick_for_sealed_bucket_is_rejected() -> None:
    b = builder(Timeframe.M1)
    feed(b, tick(ist(2026, 10, 19, 9, 15, 5), "100", 1))
    feed(b, tick(ist(2026, 10, 19, 9, 16, 5), "100", 1))  # seals 09:15
    result = b.add(tick(ist(2026, 10, 19, 9, 15, 50), "100", 1))
    assert result.rejection is not None
    assert result.rejection.reason is RejectReason.LATE_AFTER_CLOSE


def test_out_of_order_tick_within_open_bucket_is_accepted() -> None:
    b = builder(Timeframe.M1)
    feed(b, tick(ist(2026, 10, 19, 9, 15, 40), "101", 1))
    result = b.add(tick(ist(2026, 10, 19, 9, 15, 10), "99", 1))
    assert result.rejection is None
    closed = feed(b, tick(ist(2026, 10, 19, 9, 16, 0), "100", 1))
    assert closed[0].open == Decimal("99.0000")  # earliest provider_ts
    assert closed[0].close == Decimal("101.0000")  # latest provider_ts
    assert closed[0].tick_count == 2


def test_equal_timestamps_keep_first_arrival() -> None:
    b = builder(Timeframe.M1)
    at = ist(2026, 10, 19, 9, 15, 30)
    feed(b, tick(at, "100", 1), tick(at, "105", 1))
    closed = feed(b, tick(ist(2026, 10, 19, 9, 16, 0), "100", 1))
    assert closed[0].open == Decimal("100.0000")
    assert closed[0].close == Decimal("100.0000")


def test_tick_from_earlier_session_after_later_session_started_is_late() -> None:
    b = builder(Timeframe.M1)
    feed(b, tick(ist(2026, 10, 20, 9, 15, 5), "100", 1))
    result = b.add(tick(ist(2026, 10, 19, 15, 0, 0), "100", 1))
    assert result.rejection is not None
    assert result.rejection.reason is RejectReason.LATE_AFTER_CLOSE


def test_session_change_flushes_previous_session_without_carry_over() -> None:
    b = builder(Timeframe.M5)
    feed(b, tick(ist(2026, 10, 19, 15, 27, 0), "100", 1))
    closed = feed(b, tick(ist(2026, 10, 20, 9, 15, 0), "200", 1))
    assert len(closed) == 1
    assert closed[0].bar_start_ts == ist(2026, 10, 19, 15, 25)
    assert closed[0].bar_end_ts == ist(2026, 10, 19, 15, 30)


# --- gaps -----------------------------------------------------------------------------

def test_empty_intraday_bars_are_recorded_as_gaps_not_filled() -> None:
    b = builder(Timeframe.M1)
    feed(b, tick(ist(2026, 10, 19, 9, 15, 10), "100", 1))
    result = b.add(tick(ist(2026, 10, 19, 9, 18, 10), "101", 1))
    assert [g.missing_start for g in result.gaps] == [
        ist(2026, 10, 19, 9, 16), ist(2026, 10, 19, 9, 17)]
    assert all(g.missing_end - g.missing_start == timedelta(minutes=1) for g in result.gaps)
    flushed = b.flush_all()
    starts = [c.bar_start_ts for c in result.closed + flushed]
    assert ist(2026, 10, 19, 9, 16) not in starts  # no fabricated candle
    assert ist(2026, 10, 19, 9, 17) not in starts


def test_gap_bucket_becomes_sealed_against_late_arrivals() -> None:
    b = builder(Timeframe.M1)
    feed(b, tick(ist(2026, 10, 19, 9, 15, 10), "100", 1))
    b.add(tick(ist(2026, 10, 19, 9, 18, 10), "101", 1))
    result = b.add(tick(ist(2026, 10, 19, 9, 16, 30), "100", 1))
    assert result.rejection is not None
    assert result.rejection.reason is RejectReason.LATE_AFTER_CLOSE


def test_daily_timeframe_never_reports_gaps() -> None:
    b = builder(Timeframe.D1)
    result = b.add(tick(ist(2026, 10, 19, 9, 15, 10), "100", 1))
    result = b.add(tick(ist(2026, 10, 19, 14, 0, 0), "100", 1))
    assert result.gaps == []


def test_symbols_are_tracked_independently() -> None:
    b = builder(Timeframe.M1)
    feed(b, tick(ist(2026, 10, 19, 9, 15, 5), "100", 1, symbol="RELIANCE"))
    closed = feed(b, tick(ist(2026, 10, 19, 9, 16, 5), "50", 1, symbol="INFY"))
    assert closed == []
    assert len(b.open_candles("RELIANCE")) == 1
    assert len(b.open_candles("INFY")) == 1


def test_overnight_is_not_reported_as_intraday_gaps() -> None:
    # Without a reset at the session boundary, 15:29 -> 09:15 would produce ~370 fake gaps.
    b = builder(Timeframe.M1)
    feed(b, tick(ist(2026, 10, 19, 15, 29, 10), "100", 1))
    result = b.add(tick(ist(2026, 10, 20, 9, 15, 10), "100", 1))
    assert result.gaps == []

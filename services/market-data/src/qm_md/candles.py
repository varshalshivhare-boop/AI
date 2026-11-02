"""OHLCV candle builder.

Buckets are aligned to the session open (09:15 IST), not to clock minutes.
The last intraday bucket of a session is truncated at the session close (15:30 IST).
Daily candles span the whole session.

Finality rules (no wall clock is used):
  * A bucket closes when a tick for a later bucket of the same symbol arrives.
  * A bucket closes when the provider watermark (highest provider_ts seen) passes its end
    plus the grace period.
  * All open buckets close at the session boundary or when flush_all() is called.

Out-of-order policy:
  * A tick inside a still-open bucket is accepted. Open, close, high and low are taken by
    provider_ts. Equal provider_ts keeps the first arrival.
  * A tick for a bucket that has already been sealed is rejected with LATE_AFTER_CLOSE.
    Sealing means a later bucket has started, or the watermark has passed the grace period.
  * A tick from an earlier session than the current one is rejected with LATE_AFTER_CLOSE.

Gaps: an intraday bar with no ticks produces no candle. A Gap record is emitted for each
such bar. The gap is never filled, so no price is invented.

Zero volume: a bucket with ticks but total quantity 0 produces a candle with volume=0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Final

from .models import Candle, DataMode, Gap, Rejection, RejectReason, Tick, Timeframe
from .sessions import Session, SessionCalendar

DEFAULT_GRACE: Final = timedelta(seconds=2)


def bucket_bounds(
    session: Session, ts: datetime, timeframe: Timeframe
) -> tuple[datetime, datetime]:
    """Return [start, end) of the bucket containing ts. ts must lie inside the session."""
    width_minutes = timeframe.minutes
    if width_minutes is None:
        return session.open_utc, session.close_utc
    width = timedelta(minutes=width_minutes)
    index = (ts - session.open_utc) // width  # floor division on timedelta gives an int
    start = session.open_utc + index * width
    end = min(start + width, session.close_utc)
    return start, end


@dataclass(slots=True)
class _Accumulator:
    symbol: str
    exchange: str
    timeframe: Timeframe
    session_date: date
    start: datetime
    end: datetime
    data_mode: DataMode
    open_px: Decimal
    open_ts: datetime
    high: Decimal
    low: Decimal
    close_px: Decimal
    close_ts: datetime
    volume: int
    tick_count: int
    last_ingest: datetime

    @classmethod
    def from_tick(
        cls, tick: Tick, timeframe: Timeframe, session: Session, start: datetime, end: datetime
    ) -> _Accumulator:
        return cls(
            symbol=tick.symbol,
            exchange=tick.exchange,
            timeframe=timeframe,
            session_date=session.session_date,
            start=start,
            end=end,
            data_mode=tick.data_mode,
            open_px=tick.price,
            open_ts=tick.provider_ts,
            high=tick.price,
            low=tick.price,
            close_px=tick.price,
            close_ts=tick.provider_ts,
            volume=tick.quantity,
            tick_count=1,
            last_ingest=tick.ingest_ts,
        )

    def add(self, tick: Tick) -> None:
        # Strict comparisons keep the first arrival on equal timestamps.
        if tick.provider_ts < self.open_ts:
            self.open_px = tick.price
            self.open_ts = tick.provider_ts
        if tick.provider_ts > self.close_ts:
            self.close_px = tick.price
            self.close_ts = tick.provider_ts
        self.high = max(self.high, tick.price)
        self.low = min(self.low, tick.price)
        self.volume += tick.quantity
        self.tick_count += 1
        self.last_ingest = max(self.last_ingest, tick.ingest_ts)

    def to_candle(self, *, is_final: bool) -> Candle:
        return Candle(
            symbol=self.symbol,
            exchange=self.exchange,
            timeframe=self.timeframe,
            session_date=self.session_date,
            bar_start_ts=self.start,
            bar_end_ts=self.end,
            open=self.open_px,
            high=self.high,
            low=self.low,
            close=self.close_px,
            volume=self.volume,
            tick_count=self.tick_count,
            is_final=is_final,
            is_missing=False,
            provider_ts=self.close_ts,
            ingest_ts=self.last_ingest,
            data_mode=self.data_mode,
        )


@dataclass(slots=True)
class _SymbolState:
    open: dict[datetime, _Accumulator] = field(default_factory=dict)
    session_date: date | None = None
    last_seen: datetime | None = None  # latest bucket start seen in the current session
    last_closed: datetime | None = None  # buckets starting at or before this are sealed
    watermark: datetime | None = None


@dataclass(frozen=True, slots=True)
class AddResult:
    closed: list[Candle] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    rejection: Rejection | None = None


class CandleBuilder:
    def __init__(
        self,
        timeframe: Timeframe,
        calendar: SessionCalendar,
        *,
        grace: timedelta = DEFAULT_GRACE,
    ) -> None:
        self._tf = timeframe
        self._calendar = calendar
        self._grace = grace
        self._states: dict[str, _SymbolState] = {}

    @property
    def timeframe(self) -> Timeframe:
        return self._tf

    def add(self, tick: Tick) -> AddResult:
        session = self._calendar.session_for(tick.provider_ts)
        if session is None:
            return AddResult(
                rejection=Rejection(
                    reason=RejectReason.OUTSIDE_SESSION,
                    symbol=tick.symbol,
                    detail=f"{tick.provider_ts.isoformat()} is outside the regular session",
                )
            )

        state = self._states.setdefault(tick.symbol, _SymbolState())

        # An earlier session's tick arriving after a later session started is late.
        if state.session_date is not None and session.session_date < state.session_date:
            return self._late(tick, "tick belongs to an earlier session")

        start, end = bucket_bounds(session, tick.provider_ts, self._tf)
        if state.last_closed is not None and start <= state.last_closed:
            return self._late(tick, f"bucket {start.isoformat()} already sealed")

        closed: list[Candle] = []
        if state.session_date is not None and session.session_date > state.session_date:
            # No carry-over across sessions: close everything from the previous session.
            closed.extend(self._close_all(state))
            state.last_seen = None
        state.session_date = session.session_date

        # Every open bucket that starts before this one is now complete.
        for earlier in sorted(s for s in state.open if s < start):
            closed.append(self._close(state, earlier))

        gaps = self._gaps_before(tick, session, state, start)
        if state.last_seen is None or start > state.last_seen:
            state.last_seen = start
        if self._tf.minutes is not None:
            # All buckets before this one are sealed, empty or not.
            sealed_up_to = start - timedelta(minutes=self._tf.minutes)
            if state.last_closed is None or sealed_up_to > state.last_closed:
                state.last_closed = sealed_up_to

        acc = state.open.get(start)
        if acc is None:
            state.open[start] = _Accumulator.from_tick(tick, self._tf, session, start, end)
        else:
            acc.add(tick)

        if state.watermark is None or tick.provider_ts > state.watermark:
            state.watermark = tick.provider_ts
        closed.extend(self._close_due(state))
        return AddResult(closed=closed, gaps=gaps)

    def open_candles(self, symbol: str) -> list[Candle]:
        """Snapshot of unfinished buckets for live views. Never persisted or published."""
        state = self._states.get(symbol)
        if state is None:
            return []
        return [state.open[s].to_candle(is_final=False) for s in sorted(state.open)]

    def flush_all(self) -> list[Candle]:
        """Close every open bucket. Call at end of stream."""
        out: list[Candle] = []
        for symbol in sorted(self._states):
            out.extend(self._close_all(self._states[symbol]))
        return out

    # internal helpers

    def _late(self, tick: Tick, detail: str) -> AddResult:
        return AddResult(
            rejection=Rejection(
                reason=RejectReason.LATE_AFTER_CLOSE,
                symbol=tick.symbol,
                detail=f"{self._tf}: {detail}",
            )
        )

    def _gaps_before(
        self, tick: Tick, session: Session, state: _SymbolState, start: datetime
    ) -> list[Gap]:
        width_minutes = self._tf.minutes
        if width_minutes is None or state.last_seen is None or start <= state.last_seen:
            return []
        width = timedelta(minutes=width_minutes)
        gaps: list[Gap] = []
        cursor = state.last_seen + width
        while cursor < start:
            gaps.append(
                Gap(
                    symbol=tick.symbol,
                    timeframe=self._tf,
                    session_date=session.session_date,
                    missing_start=cursor,
                    missing_end=cursor + width,
                )
            )
            cursor += width
        return gaps

    def _close(self, state: _SymbolState, start: datetime) -> Candle:
        acc = state.open.pop(start)
        if state.last_closed is None or start > state.last_closed:
            state.last_closed = start
        return acc.to_candle(is_final=True)

    def _close_all(self, state: _SymbolState) -> list[Candle]:
        return [self._close(state, s) for s in sorted(state.open)]

    def _close_due(self, state: _SymbolState) -> list[Candle]:
        if state.watermark is None:
            return []
        due = [
            s
            for s in sorted(state.open)
            if state.open[s].end + self._grace <= state.watermark
        ]
        return [self._close(state, s) for s in due]

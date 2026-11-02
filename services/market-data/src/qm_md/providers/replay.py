"""Replay provider. Reads SYNTHETIC or labelled historical 1-minute CSVs and emits ticks.

Each 1-minute bar becomes four ticks: open at +0s, low at +20s, high at +40s, close at +59s.
Volume is split across the four ticks and sums exactly to the bar volume. As a result, a
candle rebuilt from these ticks matches the source bar's OHLCV exactly, which the tests rely on.

Replay output is always labelled data_mode=REPLAY. It is never LIVE.
provider_ts comes from the file. ingest_ts comes from the injected clock.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl

from ..models import DataMode, ProviderState, RawTick
from ..sessions import IST
from .base import MarketDataProvider

ALLOWED_DATA_SOURCES = frozenset({"SYNTHETIC", "HISTORICAL"})
_OFFSETS = (timedelta(0), timedelta(seconds=20), timedelta(seconds=40), timedelta(seconds=59))


@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    bar_start: datetime
    open: str
    high: str
    low: str
    close: str
    volume: int


def load_bars(path: Path) -> list[Bar]:
    """Load one 1-minute CSV. Prices stay as strings so no float rounding happens on input."""
    frame = pl.read_csv(
        path,
        schema_overrides={
            "open": pl.String,
            "high": pl.String,
            "low": pl.String,
            "close": pl.String,
            "volume": pl.Int64,
        },
    )
    sources = set(frame["data_source"].unique().to_list())
    if not sources <= ALLOWED_DATA_SOURCES:
        raise ValueError(f"{path.name}: unsupported data_source {sorted(sources)}")
    bars: list[Bar] = []
    for row in frame.iter_rows(named=True):
        bars.append(
            Bar(
                symbol=str(row["symbol"]),
                bar_start=datetime.fromisoformat(str(row["bar_start_utc"])).astimezone(UTC),
                open=str(row["open"]),
                high=str(row["high"]),
                low=str(row["low"]),
                close=str(row["close"]),
                volume=int(row["volume"]),
            )
        )
    return bars


def bar_to_ticks(bar: Bar, *, provider: str, sequence_start: int) -> list[RawTick]:
    """Expand one bar into four ticks. Returns the ticks in time order."""
    quarter = bar.volume // 4
    quantities = (quarter, quarter, quarter, bar.volume - 3 * quarter)
    prices = (bar.open, bar.low, bar.high, bar.close)
    ticks: list[RawTick] = []
    for i, (offset, price, qty) in enumerate(zip(_OFFSETS, prices, quantities, strict=True)):
        ticks.append(
            RawTick(
                symbol=bar.symbol,
                exchange="NSE",
                price=price,
                quantity=qty,
                provider_ts=bar.bar_start + offset,
                ingest_ts=bar.bar_start,  # placeholder, replaced at emission time
                provider=provider,
                data_mode=DataMode.REPLAY,
                provider_sequence=sequence_start + i,
            )
        )
    return ticks


class ReplayProvider(MarketDataProvider):
    data_mode = DataMode.REPLAY

    def __init__(
        self,
        fixture_dir: Path,
        symbols: Iterable[str],
        *,
        session_dates: Iterable[date] | None = None,
        speed: float = 0.0,
        clock: Callable[[], datetime] | None = None,
        provider_name: str = "REPLAY",
    ) -> None:
        if speed < 0:
            raise ValueError("speed must be >= 0 (0 means as fast as possible)")
        self._dir = fixture_dir
        self._symbols: set[str] = set(symbols)
        self._dates = frozenset(session_dates) if session_dates is not None else None
        self._speed = speed
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(UTC))
        self.name = provider_name
        self._state = ProviderState.DISCONNECTED
        self._bars: dict[str, list[Bar]] = {}

    def health(self) -> ProviderState:
        return self._state

    async def connect(self) -> None:
        self._state = ProviderState.CONNECTING
        self._bars = {}
        for symbol in sorted(self._symbols):
            self._bars[symbol] = self._load_symbol(symbol)
        self._state = ProviderState.CONNECTED

    async def disconnect(self) -> None:
        self._state = ProviderState.STOPPED

    async def subscribe(self, symbols: Iterable[str]) -> None:
        self._symbols.update(symbols)

    async def unsubscribe(self, symbols: Iterable[str]) -> None:
        self._symbols.difference_update(symbols)
        for symbol in list(symbols):
            self._bars.pop(symbol, None)

    def _load_symbol(self, symbol: str) -> list[Bar]:
        matches = sorted(self._dir.glob(f"SYNTHETIC_{symbol}_1m_*.csv"))
        if not matches:
            raise FileNotFoundError(f"no 1m fixture for {symbol} in {self._dir}")
        bars: list[Bar] = []
        for path in matches:
            bars.extend(load_bars(path))
        if self._dates is not None:
            bars = [b for b in bars if _ist_date(b.bar_start) in self._dates]
        return bars

    def _ordered_ticks(self) -> list[RawTick]:
        sequence = 0
        ticks: list[RawTick] = []
        for symbol in sorted(self._bars):
            for bar in self._bars[symbol]:
                expanded = bar_to_ticks(bar, provider=self.name, sequence_start=sequence)
                sequence += len(expanded)
                ticks.extend(expanded)
        ticks.sort(key=_sort_key)
        return ticks

    async def stream(self) -> AsyncIterator[RawTick]:
        if self._state is not ProviderState.CONNECTED:
            raise RuntimeError("stream() called before connect()")
        previous: datetime | None = None
        for raw in self._ordered_ticks():
            if self._speed > 0 and raw.provider_ts is not None and previous is not None:
                gap_seconds = (raw.provider_ts - previous).total_seconds()
                if gap_seconds > 0:
                    await asyncio.sleep(gap_seconds / self._speed)
            previous = raw.provider_ts
            yield raw.model_copy(update={"ingest_ts": self._clock()})


def _sort_key(tick: RawTick) -> tuple[datetime, str, int]:
    if tick.provider_ts is None:
        raise ValueError("replay ticks always carry provider_ts")
    return (tick.provider_ts, tick.symbol, tick.provider_sequence or 0)


def _ist_date(ts: datetime) -> date:
    return ts.astimezone(IST).date()

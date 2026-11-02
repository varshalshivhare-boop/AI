"""Shared test helpers. Nothing here is production code."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from qm_md.models import DataMode, Tick
from qm_md.sessions import IST, SessionCalendar

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "fixtures"
EXPECTED = Path(__file__).resolve().parent / "expected"
TEST_CALENDAR = REPO / "services" / "market-data" / "calendars" / "nse_holidays_TEST_ONLY.yaml"
PLACEHOLDER_CALENDAR = REPO / "services" / "market-data" / "calendars" / "nse_holidays.yaml"
CONTRACTS = REPO / "packages" / "contracts"
SYMBOLS = ("RELIANCE", "HDFCBANK", "INFY")
DAY = date(2026, 10, 19)


def ist(year: int, month: int, day: int, hour: int, minute: int, second: int = 0,
        microsecond: int = 0) -> datetime:
    """Build an IST wall-clock time and return it as aware UTC."""
    return datetime(year, month, day, hour, minute, second, microsecond,
                    tzinfo=IST).astimezone(UTC)


def calendar(holidays: tuple[date, ...] = ()) -> SessionCalendar:
    return SessionCalendar(calendar_version="TEST", holidays=frozenset(holidays),
                           status="POPULATED")


def tick(at: datetime, price: str | Decimal = "100", qty: int = 10, *,
         symbol: str = "RELIANCE", seq: int | None = None,
         ingest: datetime | None = None) -> Tick:
    return Tick(
        symbol=symbol,
        exchange="NSE",
        price=Decimal(price).quantize(Decimal("0.0001")),
        quantity=qty,
        provider="TEST",
        provider_ts=at,
        ingest_ts=ingest if ingest is not None else at + timedelta(milliseconds=5),
        data_mode=DataMode.REPLAY,
        provider_sequence=seq,
    )


async def run_replay(
    symbols: tuple[str, ...] = ("RELIANCE",),
    *,
    dates: tuple[date, ...] | None = (DAY,),
    timeframes: tuple[str, ...] = ("1m", "5m", "15m", "30m", "1d"),
    store: object | None = None,
    publisher: object | None = None,
    provider: object | None = None,
    metrics: object | None = None,
    publish_ticks: bool = True,
) -> object:
    """Run the real pipeline over fixtures. Returns (summary, store, metrics)."""
    from datetime import datetime as _dt

    from support import TEST_CALENDAR

    from qm_md.candles import CandleBuilder
    from qm_md.dedupe import LruDeduper
    from qm_md.metrics import MarketDataMetrics
    from qm_md.models import Timeframe
    from qm_md.normalize import TickNormalizer
    from qm_md.pipeline import MarketDataPipeline
    from qm_md.providers.replay import ReplayProvider
    from qm_md.sessions import SessionCalendar
    from qm_md.store import InMemoryCandleStore

    cal = SessionCalendar.from_yaml(TEST_CALENDAR, allow_test=True)
    m = metrics if metrics is not None else MarketDataMetrics()
    st = store if store is not None else InMemoryCandleStore()
    prov = provider if provider is not None else ReplayProvider(
        FIXTURES, symbols, session_dates=dates, speed=0.0, clock=lambda: _dt.now(UTC))
    pipeline = MarketDataPipeline(
        provider=prov,  # type: ignore[arg-type]
        normalizer=TickNormalizer(symbols),
        deduper=LruDeduper(100_000),
        builders=[CandleBuilder(Timeframe(tf), cal) for tf in timeframes],
        store=st,  # type: ignore[arg-type]
        metrics=m,  # type: ignore[arg-type]
        clock=lambda: _dt.now(UTC),
        publisher=publisher,  # type: ignore[arg-type]
        publish_ticks=publish_ticks,
    )
    summary = await pipeline.run()
    return summary, st, m

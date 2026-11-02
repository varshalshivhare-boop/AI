"""Internal domain models. Wire formats are defined by packages/contracts, not here."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class DataMode(StrEnum):
    LIVE = "LIVE"
    REPLAY = "REPLAY"
    DEMO = "DEMO"
    HISTORICAL = "HISTORICAL"


class Timeframe(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    D1 = "1d"

    @property
    def minutes(self) -> int | None:
        """Bar width in minutes. None for the daily timeframe, which spans the session."""
        match self:
            case Timeframe.M1:
                return 1
            case Timeframe.M5:
                return 5
            case Timeframe.M15:
                return 15
            case Timeframe.M30:
                return 30
            case Timeframe.D1:
                return None


class ProviderState(StrEnum):
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
    STOPPED = "STOPPED"


class RejectReason(StrEnum):
    UNKNOWN_SYMBOL = "UNKNOWN_SYMBOL"
    UNSUPPORTED_EXCHANGE = "UNSUPPORTED_EXCHANGE"
    INVALID_PRICE = "INVALID_PRICE"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    MISSING_PROVIDER_TS = "MISSING_PROVIDER_TS"
    NAIVE_TIMESTAMP = "NAIVE_TIMESTAMP"
    FUTURE_TIMESTAMP = "FUTURE_TIMESTAMP"
    DUPLICATE = "DUPLICATE"
    OUTSIDE_SESSION = "OUTSIDE_SESSION"
    LATE_AFTER_CLOSE = "LATE_AFTER_CLOSE"


class RawTick(BaseModel):
    """A tick as delivered by a provider, before validation. Price arrives as a string."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    exchange: str
    price: str
    quantity: int
    provider_ts: datetime | None
    ingest_ts: datetime
    provider: str
    data_mode: DataMode
    provider_sequence: int | None = None
    cumulative_volume: int | None = None


class Tick(BaseModel):
    """A validated, normalized tick. All timestamps are timezone-aware UTC."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    exchange: str
    price: Decimal
    quantity: int
    provider: str
    provider_ts: datetime
    ingest_ts: datetime
    data_mode: DataMode
    provider_sequence: int | None = None
    cumulative_volume: int | None = None


class Rejection(BaseModel):
    model_config = ConfigDict(frozen=True)

    reason: RejectReason
    symbol: str
    detail: str


class Candle(BaseModel):
    """A candle. Only is_final=True candles are persisted or published."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    exchange: str
    timeframe: Timeframe
    session_date: date
    bar_start_ts: datetime
    bar_end_ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    tick_count: int
    is_final: bool
    is_missing: bool
    provider_ts: datetime | None
    ingest_ts: datetime
    data_mode: DataMode


class Gap(BaseModel):
    """A bar that received no ticks inside a session. No candle is fabricated for it."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: Timeframe
    session_date: date
    missing_start: datetime
    missing_end: datetime

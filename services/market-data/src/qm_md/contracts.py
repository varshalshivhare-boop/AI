"""Mapping from internal models to the wire payloads defined in packages/contracts.

Payload field names and types must match the v1 JSON Schemas. Tests validate every payload.
Prices are decimal strings, never JSON numbers.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from .models import Candle, DataMode, ProviderState, Tick

SCHEMA_VERSION = 1


def _price(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.0001")), "f")


def _ts(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def tick_payload(tick: Tick) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "symbol": tick.symbol,
        "exchange": tick.exchange,
        "price": _price(tick.price),
        "quantity": tick.quantity,
        "cumulative_volume": tick.cumulative_volume,
        "provider": tick.provider,
        "provider_sequence": tick.provider_sequence,
        "provider_ts": _ts(tick.provider_ts),
        "ingest_ts": _ts(tick.ingest_ts),
        "data_mode": tick.data_mode.value,
    }


def candle_payload(candle: Candle) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "symbol": candle.symbol,
        "exchange": candle.exchange,
        "timeframe": candle.timeframe.value,
        "session_date": candle.session_date.isoformat(),
        "bar_start_ts": _ts(candle.bar_start_ts),
        "bar_end_ts": _ts(candle.bar_end_ts),
        "open": _price(candle.open),
        "high": _price(candle.high),
        "low": _price(candle.low),
        "close": _price(candle.close),
        "volume": candle.volume,
        "tick_count": candle.tick_count,
        "is_final": candle.is_final,
        "is_missing": candle.is_missing,
        "provider_ts": _ts(candle.provider_ts),
        "ingest_ts": _ts(candle.ingest_ts),
        "data_mode": candle.data_mode.value,
    }


def health_payload(
    *,
    provider: str,
    state: ProviderState,
    previous_state: ProviderState | None,
    reason_code: str | None,
    last_tick_provider_ts: datetime | None,
    seconds_since_last_tick: float | None,
    reconnect_attempt: int,
    ingest_ts: datetime,
    data_mode: DataMode,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "state": state.value,
        "previous_state": previous_state.value if previous_state is not None else None,
        "reason_code": reason_code,
        "last_tick_provider_ts": _ts(last_tick_provider_ts),
        "seconds_since_last_tick": seconds_since_last_tick,
        "reconnect_attempt": reconnect_attempt,
        "provider_ts": None,
        "ingest_ts": _ts(ingest_ts),
        "data_mode": data_mode.value,
    }

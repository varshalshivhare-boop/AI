"""Candle persistence. Idempotent: re-writing the same candle is a no-op on content."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol

import asyncpg

from .errors import StorageError
from .models import Candle

logger = logging.getLogger("qm_md.store")


class CandleStore(Protocol):
    async def upsert_many(self, candles: Sequence[Candle]) -> int: ...


def _check_final(candles: Sequence[Candle]) -> None:
    for candle in candles:
        if not candle.is_final:
            raise ValueError(
                f"refusing to persist an open candle: {candle.symbol} {candle.timeframe}"
            )


class InMemoryCandleStore:
    """Keyed by (symbol, timeframe, bar_start). Used by tests and by runs without a database."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, object], Candle] = {}

    async def upsert_many(self, candles: Sequence[Candle]) -> int:
        _check_final(candles)
        for candle in candles:
            self.rows[(candle.symbol, candle.timeframe.value, candle.bar_start_ts)] = candle
        return len(candles)

    def sorted_rows(self) -> list[Candle]:
        return sorted(self.rows.values(),
                      key=lambda c: (c.symbol, c.timeframe.value, c.bar_start_ts))


_UPSERT_SQL = """
INSERT INTO candles (ts, instrument_id, timeframe, open, high, low, close, volume,
                     tick_count, is_final, is_missing, data_mode, provider_ts, ingest_ts,
                     schema_version)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, 1)
ON CONFLICT (instrument_id, timeframe, ts) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    tick_count = EXCLUDED.tick_count,
    is_final = EXCLUDED.is_final,
    is_missing = EXCLUDED.is_missing,
    data_mode = EXCLUDED.data_mode,
    provider_ts = EXCLUDED.provider_ts,
    ingest_ts = EXCLUDED.ingest_ts
"""


async def instrument_id_for(
    conn: asyncpg.Connection,
    cache: dict[tuple[str, str], int],
    symbol: str,
    exchange: str,
) -> int:
    """Return instruments.instrument_id, creating the row on first use."""
    key = (exchange, symbol)
    cached = cache.get(key)
    if cached is not None:
        return cached
    value = await conn.fetchval(
        """
        INSERT INTO instruments (exchange, segment, symbol)
        VALUES ($1, 'CASH_EQUITY', $2)
        ON CONFLICT (exchange, segment, symbol)
        DO UPDATE SET updated_at = instruments.updated_at
        RETURNING instrument_id
        """,
        exchange,
        symbol,
    )
    instrument_id = int(value)
    cache[key] = instrument_id
    return instrument_id


class PostgresCandleStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._instrument_ids: dict[tuple[str, str], int] = {}

    async def upsert_many(self, candles: Sequence[Candle]) -> int:
        _check_final(candles)
        if not candles:
            return 0
        try:
            async with self._pool.acquire() as conn, conn.transaction():
                rows = []
                for c in candles:
                    instrument_id = await instrument_id_for(
                        conn, self._instrument_ids, c.symbol, c.exchange
                    )
                    rows.append((
                        c.bar_start_ts, instrument_id, c.timeframe.value, c.open, c.high,
                        c.low, c.close, c.volume, c.tick_count, c.is_final, c.is_missing,
                        c.data_mode.value, c.provider_ts, c.ingest_ts,
                    ))
                await conn.executemany(_UPSERT_SQL, rows)
        except asyncpg.PostgresError as exc:
            logger.error("candle upsert failed", exc_info=True,
                         extra={"event": "store_error", "count": len(candles)})
            raise StorageError(f"candle upsert failed: {exc}") from exc
        return len(candles)

"""Integration: real PostgreSQL with migration 0001. Set TEST_DATABASE_URL to run."""

import os
import uuid
from decimal import Decimal

import asyncpg
import pytest
from support import DAY, ist

from qm_md.errors import StorageError
from qm_md.models import Candle, DataMode, Timeframe
from qm_md.store import PostgresCandleStore

pytestmark = pytest.mark.integration

URL = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


def candle(symbol: str, minute: int, close: str = "100.5", *, final: bool = True) -> Candle:
    start = ist(2026, 10, 19, 9, 15 + minute)
    return Candle(
        symbol=symbol, exchange="NSE", timeframe=Timeframe.M1, session_date=DAY,
        bar_start_ts=start, bar_end_ts=start.replace(second=0) + (ist(2026, 10, 19, 9, 16)
                                                                 - ist(2026, 10, 19, 9, 15)),
        open=Decimal("100"), high=Decimal("101"), low=Decimal("99.5"), close=Decimal(close),
        volume=500, tick_count=4, is_final=final, is_missing=False,
        provider_ts=start, ingest_ts=start, data_mode=DataMode.REPLAY,
    )


@pytest.fixture
async def pool():  # type: ignore[no-untyped-def]
    if not URL:
        pytest.skip("TEST_DATABASE_URL not set")
    p = await asyncpg.create_pool(URL, min_size=1, max_size=2)
    yield p
    await p.close()


@pytest.fixture
async def symbol(pool):  # type: ignore[no-untyped-def]
    name = f"T{uuid.uuid4().hex[:8].upper()}"
    yield name
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM candles WHERE instrument_id IN "
            "(SELECT instrument_id FROM instruments WHERE symbol = $1)", name)
        await conn.execute("DELETE FROM instruments WHERE symbol = $1", name)


@needs_db
async def test_upsert_is_idempotent(pool, symbol) -> None:  # type: ignore[no-untyped-def]
    store = PostgresCandleStore(pool)
    batch = [candle(symbol, m) for m in range(5)]
    assert await store.upsert_many(batch) == 5
    assert await store.upsert_many(batch) == 5  # same content again
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM candles c JOIN instruments i USING (instrument_id) "
            "WHERE i.symbol = $1", symbol)
    assert count == 5


@needs_db
async def test_upsert_updates_changed_values(pool, symbol) -> None:  # type: ignore[no-untyped-def]
    store = PostgresCandleStore(pool)
    await store.upsert_many([candle(symbol, 0, close="100.5")])
    await store.upsert_many([candle(symbol, 0, close="100.75")])
    async with pool.acquire() as conn:
        close = await conn.fetchval(
            "SELECT c.close FROM candles c JOIN instruments i USING (instrument_id) "
            "WHERE i.symbol = $1", symbol)
    assert close == Decimal("100.7500")


@needs_db
async def test_instrument_row_is_created_once(pool, symbol) -> None:  # type: ignore[no-untyped-def]
    store = PostgresCandleStore(pool)
    await store.upsert_many([candle(symbol, 0)])
    await store.upsert_many([candle(symbol, 1)])
    async with pool.acquire() as conn:
        n = await conn.fetchval("SELECT count(*) FROM instruments WHERE symbol = $1", symbol)
    assert n == 1


@needs_db
async def test_open_candles_are_refused_before_touching_the_database(  # type: ignore[no-untyped-def]
    pool, symbol,
) -> None:
    store = PostgresCandleStore(pool)
    with pytest.raises(ValueError, match="open candle"):
        await store.upsert_many([candle(symbol, 0, final=False)])


@needs_db
async def test_database_errors_become_storage_errors(pool, symbol) -> None:  # type: ignore[no-untyped-def]
    store = PostgresCandleStore(pool)
    bad = candle(symbol, 0).model_copy(update={"volume": -1})  # violates CHECK volume >= 0
    with pytest.raises(StorageError):
        await store.upsert_many([bad])



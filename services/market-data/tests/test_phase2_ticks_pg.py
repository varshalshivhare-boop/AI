"""Milestone 2.2 acceptance: flag off writes zero rows; flag on writes one row per accepted tick."""

import os
import uuid
from datetime import timedelta

import asyncpg
import pytest

from qm_md.ticks import TickWriter
from support import DAY, run_replay, tick, ist
from qm_md.errors import StorageError

pytestmark = pytest.mark.integration
URL = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture
async def pool():  # type: ignore[no-untyped-def]
    if not URL:
        pytest.skip("TEST_DATABASE_URL not set")
    p = await asyncpg.create_pool(URL, min_size=1, max_size=2)
    yield p
    await p.close()


async def count_ticks(pool, symbol: str) -> int:  # type: ignore[no-untyped-def]
    async with pool.acquire() as conn:
        return int(await conn.fetchval(
            "SELECT count(*) FROM ticks t JOIN instruments i USING (instrument_id) "
            "WHERE i.symbol = $1", symbol))


async def cleanup(pool, symbol: str) -> None:  # type: ignore[no-untyped-def]
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM ticks WHERE instrument_id IN (SELECT instrument_id FROM instruments "
            "WHERE symbol = $1)", symbol)
        await conn.execute("DELETE FROM instruments WHERE symbol = $1", symbol)


@needs_db
async def test_writer_persists_every_tick_and_flushes_on_close(pool) -> None:  # type: ignore[no-untyped-def]
    symbol = f"T{uuid.uuid4().hex[:8].upper()}"
    try:
        writer = TickWriter(pool, batch_size=50)
        for i in range(120):
            t = tick(ist(2026, 10, 19, 9, 15, 0) + timedelta(milliseconds=i), "100", 1,
                     symbol=symbol, seq=i + 1)
            await writer.add(t)
        await writer.close()
        assert writer.rows_written == 120
        assert await count_ticks(pool, symbol) == 120
        # Re-writing the same keys adds nothing.
        writer2 = TickWriter(pool, batch_size=1)
        await writer2.add(tick(ist(2026, 10, 19, 9, 15, 0), "100", 1, symbol=symbol, seq=1))
        assert await count_ticks(pool, symbol) == 120
    finally:
        await cleanup(pool, symbol)


@needs_db
async def test_tick_without_sequence_is_refused_not_dropped(pool) -> None:  # type: ignore[no-untyped-def]
    writer = TickWriter(pool)
    with pytest.raises(ValueError, match="no provider_sequence"):
        await writer.add(tick(ist(2026, 10, 19, 9, 15), "100", 1, seq=None))


@needs_db
async def test_database_failure_is_a_storage_error(pool) -> None:  # type: ignore[no-untyped-def]
    symbol = f"T{uuid.uuid4().hex[:8].upper()}"
    try:
        writer = TickWriter(pool, batch_size=1)
        bad = tick(ist(2026, 10, 19, 9, 15), "100", -1, symbol=symbol, seq=1)  # quantity < 0
        with pytest.raises(StorageError):
            await writer.add(bad)
    finally:
        await cleanup(pool, symbol)


@needs_db
async def test_replay_with_persistence_off_writes_zero_tick_rows(pool) -> None:  # type: ignore[no-untyped-def]
    before = await count_ticks(pool, "RELIANCE")
    await run_replay(("RELIANCE",), dates=(DAY,), timeframes=("1m",))  # no tick_writer passed
    assert await count_ticks(pool, "RELIANCE") == before


@needs_db
async def test_replay_with_persistence_on_writes_one_row_per_accepted_tick(pool) -> None:  # type: ignore[no-untyped-def]
    symbol = "RELIANCE"
    before = await count_ticks(pool, symbol)
    try:
        summary, _, _ = await run_replay(("RELIANCE",), dates=(DAY,), timeframes=("1m",),
                                         tick_writer=TickWriter(pool, batch_size=200))
        assert await count_ticks(pool, symbol) - before == summary.ticks_accepted  # type: ignore[attr-defined]
    finally:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM ticks WHERE instrument_id IN (SELECT instrument_id FROM instruments "
                "WHERE symbol = $1) AND provider_ts >= $2 AND provider_ts < $3",
                symbol, ist(2026, 10, 19, 9, 15), ist(2026, 10, 19, 15, 30))

"""Optional raw tick persistence. Off by default; enabled only with the licence flag (see settings).

Rows are written in batches. A batch is flushed when it reaches batch_size, when the oldest
buffered tick is older than flush_interval, or on close(). A failed flush raises StorageError.
The buffer is kept on failure, and the pipeline treats the error as fatal.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import asyncpg

from .errors import StorageError
from .models import Tick
from .store import instrument_id_for

logger = logging.getLogger("qm_md.ticks")

_INSERT_SQL = """
INSERT INTO ticks (provider_ts, instrument_id, ingest_ts, price, quantity,
                   provider_sequence, data_mode, schema_version)
VALUES ($1, $2, $3, $4, $5, $6, $7, 1)
ON CONFLICT DO NOTHING
"""


class TickWriter:
    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        batch_size: int = 500,
        flush_interval: timedelta = timedelta(milliseconds=500),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self._pool = pool
        self._batch_size = batch_size
        self._interval = flush_interval
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(UTC))
        self._buffer: list[Tick] = []
        self._first_buffered_at: datetime | None = None
        self._instrument_ids: dict[tuple[str, str], int] = {}
        self.rows_written = 0

    @property
    def buffered(self) -> int:
        return len(self._buffer)

    async def add(self, tick: Tick) -> None:
        if tick.provider_sequence is None:
            # ticks.provider_sequence is NOT NULL and part of the primary key.
            raise ValueError(f"tick for {tick.symbol} has no provider_sequence; cannot persist it")
        now = self._clock()
        if self._first_buffered_at is None:
            self._first_buffered_at = now
        self._buffer.append(tick)
        due = now - self._first_buffered_at >= self._interval
        if len(self._buffer) >= self._batch_size or due:
            await self.flush()

    async def flush(self) -> None:
        if not self._buffer:
            return
        batch = self._buffer
        try:
            async with self._pool.acquire() as conn, conn.transaction():
                rows = []
                for t in batch:
                    instrument_id = await instrument_id_for(
                        conn, self._instrument_ids, t.symbol, t.exchange
                    )
                    rows.append((
                        t.provider_ts, instrument_id, t.ingest_ts, t.price, t.quantity,
                        t.provider_sequence, t.data_mode.value,
                    ))
                await conn.executemany(_INSERT_SQL, rows)
        except asyncpg.PostgresError as exc:
            logger.error("tick flush failed", exc_info=True,
                         extra={"event": "tick_flush_error", "count": len(batch)})
            raise StorageError(f"tick flush failed: {exc}") from exc
        self.rows_written += len(batch)
        self._buffer = []
        self._first_buffered_at = None

    async def close(self) -> None:
        await self.flush()

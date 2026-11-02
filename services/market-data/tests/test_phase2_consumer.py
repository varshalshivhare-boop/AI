"""Milestone 2.7: a reference consumer proves the stream contract the PC 3 gateway will rely on.

Valid candles are ACKed. A malformed payload is moved to dlq.candles.closed.1m with the error.
"""

import json

import pytest
import redis
import redis.asyncio as aioredis
from jsonschema import Draft202012Validator, FormatChecker
from redis.backoff import NoBackoff
from redis.retry import Retry

from qm_md.metrics import MarketDataMetrics
from qm_md.publish import RedisPublisher
from support import CONTRACTS, DAY, run_replay

pytestmark = pytest.mark.integration

STREAM = "candles.closed.1m"
GROUP = "gateway"
DLQ = "dlq.candles.closed.1m"


def reference_consumer(sync: redis.Redis) -> dict[str, int]:
    schema = Draft202012Validator(
        json.loads((CONTRACTS / "candle.closed.v1.json").read_text()),
        format_checker=FormatChecker(),
    )
    acked = 0
    dead = 0
    while True:
        batch = sync.xreadgroup(GROUP, "c1", {STREAM: ">"}, count=500, block=100)
        if not batch:
            break
        for _stream, entries in batch:
            for entry_id, fields in entries:
                raw = fields[b"payload"].decode()
                try:
                    schema.validate(json.loads(raw))
                except Exception as exc:  # noqa: BLE001 - every failure goes to the DLQ
                    sync.xadd(DLQ, {"payload": raw, "error": str(exc)[:500],
                                    "source_id": entry_id})
                    dead += 1
                else:
                    acked += 1
                sync.xack(STREAM, GROUP, entry_id)
    return {"acked": acked, "dead_lettered": dead}


async def test_valid_candles_are_acked_and_malformed_ones_dead_lettered(redis_server) -> None:  # type: ignore[no-untyped-def]
    sync = redis.Redis.from_url(redis_server.url, decode_responses=False)
    sync.flushall()
    try:
        sync.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except redis.ResponseError:
        pass

    client = aioredis.Redis.from_url(redis_server.url, socket_connect_timeout=0.5,
                                     retry=Retry(NoBackoff(), 0))
    try:
        await run_replay(("RELIANCE",), dates=(DAY,), timeframes=("1m",),
                         publisher=RedisPublisher(client, MarketDataMetrics()),
                         metrics=MarketDataMetrics())
    finally:
        await client.aclose()

    # One malformed payload: price as a JSON number instead of a decimal string.
    bad = {"schema_version": 1, "symbol": "RELIANCE", "exchange": "NSE", "timeframe": "1m",
           "session_date": "2026-10-19", "bar_start_ts": "2026-10-19T03:45:00+00:00",
           "bar_end_ts": "2026-10-19T03:46:00+00:00", "open": 1381.75, "high": "1381.75",
           "low": "1380.90", "close": "1380.90", "volume": 1, "tick_count": 1,
           "is_final": True, "is_missing": False, "provider_ts": None,
           "ingest_ts": "2026-10-19T03:46:00+00:00", "data_mode": "REPLAY"}
    sync.xadd(STREAM, {"payload": json.dumps(bad)})

    result = reference_consumer(sync)

    assert result["dead_lettered"] == 1
    assert result["acked"] == 375
    pending = sync.xpending(STREAM, GROUP)
    assert pending["pending"] == 0
    assert sync.xlen(DLQ) == 1
    dlq_entry = sync.xrange(DLQ)[0][1]
    assert b"price" in dlq_entry[b"error"] or b"1381.75" in dlq_entry[b"payload"]

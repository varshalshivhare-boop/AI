"""Integration: real redis-server. Skipped automatically when redis-server is not installed."""

import json
import logging
from collections.abc import AsyncIterator

import pytest
import redis
import redis.asyncio as aioredis
from jsonschema import Draft202012Validator, FormatChecker
from redis.backoff import NoBackoff
from redis.retry import Retry
from support import CONTRACTS, DAY, FIXTURES, run_replay

from qm_md.metrics import MarketDataMetrics
from qm_md.models import RawTick
from qm_md.providers.replay import ReplayProvider
from qm_md.publish import RedisPublisher

pytestmark = pytest.mark.integration


def _client(url: str) -> aioredis.Redis:
    return aioredis.Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5,
                                   retry=Retry(NoBackoff(), 0))


def _schema(name: str) -> Draft202012Validator:
    doc = json.loads((CONTRACTS / f"{name}.v1.json").read_text())
    return Draft202012Validator(doc, format_checker=FormatChecker())


def _payloads(sync: redis.Redis, stream: str) -> list[dict[str, object]]:
    entries = sync.xrange(stream)
    return [json.loads(fields[b"payload"]) for _id, fields in entries]


async def test_full_day_publishes_contract_valid_payloads(redis_server) -> None:  # type: ignore[no-untyped-def]
    sync = redis.Redis.from_url(redis_server.url)
    sync.flushall()
    client = _client(redis_server.url)
    try:
        metrics = MarketDataMetrics()
        publisher = RedisPublisher(client, metrics)
        summary, _store, _m = await run_replay(("RELIANCE",), dates=(DAY,), publisher=publisher,
                                               metrics=metrics)
    finally:
        await client.aclose()

    assert summary.publish_failures == 0  # type: ignore[attr-defined]
    assert sync.xlen("ticks.normalized") == 1500
    assert sync.xlen("candles.closed.1m") == 375
    assert sync.xlen("candles.closed.5m") == 75
    assert sync.xlen("candles.closed.1d") == 1
    assert sync.xlen("provider.health") == 2

    for payload in _payloads(sync, "ticks.normalized"):
        _schema("tick.normalized").validate(payload)
        assert payload["data_mode"] == "REPLAY"
    for tf in ("1m", "5m", "1d"):
        for payload in _payloads(sync, f"candles.closed.{tf}"):
            _schema("candle.closed").validate(payload)
            assert payload["data_mode"] == "REPLAY"
            assert payload["is_final"] is True
    for payload in _payloads(sync, "provider.health"):
        _schema("provider_health").validate(payload)


async def test_tick_stream_is_trimmed_to_maxlen(redis_server) -> None:  # type: ignore[no-untyped-def]
    sync = redis.Redis.from_url(redis_server.url)
    sync.flushall()
    client = _client(redis_server.url)
    try:
        publisher = RedisPublisher(client, MarketDataMetrics(), ticks_maxlen=100)
        await run_replay(("RELIANCE",), dates=(DAY,), timeframes=("1m",), publisher=publisher)
    finally:
        await client.aclose()
    length = sync.xlen("ticks.normalized")
    assert length < 1500
    assert length <= 200  # approximate trimming may keep a little more than maxlen


async def test_redis_killed_mid_replay_is_logged_metered_and_not_fatal(  # type: ignore[no-untyped-def]
    redis_server, caplog,
) -> None:
    class KillingReplay(ReplayProvider):
        async def stream(self) -> AsyncIterator[RawTick]:  # type: ignore[override]
            count = 0
            async for tick in super().stream():
                count += 1
                if count == 300:
                    redis_server.kill()
                yield tick

    client = _client(redis_server.url)
    metrics = MarketDataMetrics()
    publisher = RedisPublisher(client, metrics)
    provider = KillingReplay(FIXTURES, ("RELIANCE",), session_dates=(DAY,), speed=0.0)
    caplog.set_level(logging.ERROR, logger="qm_md.publish")
    try:
        summary, store, _m = await run_replay(
            ("RELIANCE",), dates=(DAY,), timeframes=("1m",), publisher=publisher,
            provider=provider, metrics=metrics,
        )
    finally:
        await client.aclose()

    # The run completes. Persistence is unaffected: the candles table is the system of record.
    assert summary.ticks_received == 1500  # type: ignore[attr-defined]
    assert len(store.rows) == 375  # type: ignore[attr-defined]
    # Failures are counted and logged, not raised.
    assert summary.publish_failures > 0  # type: ignore[attr-defined]
    failed = metrics.redis_publish_errors.labels(stream="ticks.normalized")._value.get()  # type: ignore[attr-defined]
    assert failed > 0
    assert any("redis publish failed" in r.getMessage() for r in caplog.records)
    assert all(r.exc_info for r in caplog.records if "redis publish failed" in r.getMessage())


async def test_unreachable_redis_from_the_start_does_not_crash_the_run(caplog) -> None:  # type: ignore[no-untyped-def]
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]
    client = _client(f"redis://127.0.0.1:{dead_port}/0")
    metrics = MarketDataMetrics()
    publisher = RedisPublisher(client, metrics)
    try:
        summary, store, _ = await run_replay(
            ("RELIANCE",), dates=(DAY,), timeframes=("1m",), publisher=publisher, metrics=metrics,
        )
    finally:
        await client.aclose()
    assert summary.publish_failures > 0  # type: ignore[attr-defined]
    assert len(store.rows) == 375  # type: ignore[attr-defined]


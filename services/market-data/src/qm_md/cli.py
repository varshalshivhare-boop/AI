"""Command line entry points.

  python -m qm_md replay --calendar calendars/nse_holidays_TEST_ONLY.yaml \
      --allow-test-calendar --symbols RELIANCE --date 2026-10-19 --speed 0 \
      --output-dir ../../fixtures/out
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from .candles import CandleBuilder
from .dedupe import LruDeduper
from .errors import ConfigurationError
from .golden import write_candles_csv
from .logging_setup import setup_logging
from .metrics import MarketDataMetrics
from .models import Timeframe
from .normalize import TickNormalizer
from .pipeline import MarketDataPipeline
from .providers.replay import ReplayProvider
from .sessions import SessionCalendar
from .store import InMemoryCandleStore

logger = logging.getLogger("qm_md.cli")
REPO_ROOT = Path(__file__).resolve().parents[4]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="qm_md")
    sub = parser.add_subparsers(dest="command", required=True)
    replay = sub.add_parser("replay", help="replay SYNTHETIC or labelled fixtures")
    replay.add_argument("--fixture-dir", type=Path, default=REPO_ROOT / "fixtures")
    replay.add_argument("--symbols", required=True, help="comma-separated, e.g. RELIANCE,INFY")
    replay.add_argument("--date", action="append", type=date.fromisoformat, dest="dates",
                        help="session date (repeatable). Default: all dates in the fixture")
    replay.add_argument("--speed", type=float, default=0.0, help="1, 10, or 0 for max speed")
    replay.add_argument("--calendar", type=Path, required=True)
    replay.add_argument("--allow-test-calendar", action="store_true")
    replay.add_argument("--timeframes", default="1m,5m,15m,30m,1d")
    replay.add_argument("--redis-url", default=os.environ.get("REDIS_URL"))
    replay.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    replay.add_argument("--output-dir", type=Path, default=None)
    replay.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"))
    sub.add_parser("serve", help="run the pipeline and HTTP endpoints; configured by environment")
    return parser.parse_args(argv)


async def _replay(args: argparse.Namespace) -> int:
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    calendar = SessionCalendar.from_yaml(args.calendar, allow_test=args.allow_test_calendar)
    timeframes = [Timeframe(tf.strip()) for tf in args.timeframes.split(",")]
    metrics = MarketDataMetrics()

    provider = ReplayProvider(
        args.fixture_dir, symbols, session_dates=args.dates, speed=args.speed,
        clock=lambda: datetime.now(UTC),
    )
    normalizer = TickNormalizer(symbols)
    builders = [CandleBuilder(tf, calendar) for tf in timeframes]

    if args.database_url:
        import asyncpg

        from .store import PostgresCandleStore
        pool = await asyncpg.create_pool(args.database_url, min_size=1, max_size=4)
        store: InMemoryCandleStore | PostgresCandleStore = PostgresCandleStore(pool)
    else:
        logger.warning("no DATABASE_URL: candles are kept in memory only",
                       extra={"event": "no_database"})
        store = InMemoryCandleStore()

    publisher = None
    redis_client = None
    if args.redis_url:
        from redis.asyncio import Redis
        from redis.backoff import NoBackoff
        from redis.retry import Retry

        from .publish import RedisPublisher
        redis_client = Redis.from_url(
            args.redis_url, socket_connect_timeout=0.5, socket_timeout=0.5,
            retry=Retry(NoBackoff(), 0),
        )
        publisher = RedisPublisher(redis_client, metrics)

    pipeline = MarketDataPipeline(
        provider=provider, normalizer=normalizer, deduper=LruDeduper(100_000),
        builders=builders, store=store, metrics=metrics,
        clock=lambda: datetime.now(UTC), publisher=publisher,
    )
    try:
        summary = await pipeline.run()
    finally:
        if redis_client is not None:
            await redis_client.aclose()

    if args.output_dir is not None and isinstance(store, InMemoryCandleStore):
        for tf in timeframes:
            rows = [c for c in store.sorted_rows() if c.timeframe is tf]
            write_candles_csv(args.output_dir / f"candles_{tf.value}.csv", rows)
    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "serve":
        from .serve import EXIT_FAILED, serve_main
        from .settings import load_settings

        env = dict(os.environ)
        try:
            settings = load_settings(env)
        except ConfigurationError as exc:
            setup_logging("ERROR")
            logger.error("configuration error: %s", exc, extra={"event": "config_error"})
            return EXIT_FAILED
        setup_logging(settings.log_level)
        return serve_main(settings, env)
    setup_logging(args.log_level)
    if args.command == "replay":
        return asyncio.run(_replay(args))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

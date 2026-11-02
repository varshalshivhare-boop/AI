"""Long-running service: pipeline plus health, readiness and metrics endpoints in one process.

Lifecycle:
  * The pipeline starts. When the provider's stream ends, the pipeline finishes but the process
    keeps serving /health, /ready and /metrics until a stop signal arrives. This lets an operator
    inspect a finished replay.
  * SIGTERM or SIGINT: request a pipeline stop, wait up to SHUTDOWN_TIMEOUT_SECONDS for the
    flush to complete, stop the HTTP server, close connections, exit 0.
  * Timeout: exit 1 and log the state. Pipeline failure: exit 1.

Windows: asyncio cannot install signal handlers there. Ctrl+C then cancels the run without the
flush, and the process exits with code 130. Use Linux or Docker for graceful stops.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from datetime import timedelta
from pathlib import Path
from typing import Any

import uvicorn

from .api import create_app, redis_check
from .candles import CandleBuilder
from .dedupe import LruDeduper
from .errors import ConfigurationError
from .metrics import MarketDataMetrics
from .models import Timeframe
from .normalize import TickNormalizer
from .pipeline import LivenessConfig, MarketDataPipeline
from .providers.base import MarketDataProvider
from .providers.replay import ReplayProvider
from .providers.upstox import UpstoxConfig, UpstoxProvider
from .publish import OpenCandleThrottle, RedisPublisher
from .sessions import SessionCalendar
from .settings import Settings
from .store import PostgresCandleStore
from .ticks import TickWriter

logger = logging.getLogger("qm_md.serve")
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_INTERRUPTED = 130


class _Server(uvicorn.Server):
    """uvicorn installs its own signal handlers by default. We own signals, so turn them off."""

    def capture_signals(self) -> contextlib.AbstractContextManager[None]:  # type: ignore[override]
        return contextlib.nullcontext()


def _build_provider(settings: Settings, env: dict[str, str]) -> MarketDataProvider:
    if settings.provider == "REPLAY":
        return ReplayProvider(
            settings.fixture_dir, settings.watchlist, speed=settings.replay_speed,
            clock=_utcnow,
        )
    if settings.provider == "UPSTOX":
        return UpstoxProvider(UpstoxConfig.from_env(env))
    raise ConfigurationError(f"unknown MARKET_DATA_PROVIDER {settings.provider!r}")


def _utcnow() -> Any:
    from datetime import UTC, datetime

    return datetime.now(UTC)


async def run_service(settings: Settings, env: dict[str, str]) -> int:
    import asyncpg
    from redis.asyncio import Redis
    from redis.backoff import NoBackoff
    from redis.retry import Retry

    calendar = SessionCalendar.from_yaml(
        Path(settings.calendar_path), allow_test=_allow_test(env)
    )
    provider = _build_provider(settings, env)
    metrics = MarketDataMetrics()
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=4)
    redis_client = Redis.from_url(
        settings.redis_url, socket_connect_timeout=0.5, socket_timeout=0.5,
        retry=Retry(NoBackoff(), 0),
    )
    stop_event = asyncio.Event()
    exit_code = EXIT_OK
    server: _Server | None = None
    server_task: asyncio.Task[None] | None = None
    try:
        tick_writer = (
            TickWriter(pool, batch_size=settings.tick_batch_size,
                       flush_interval=timedelta(milliseconds=settings.tick_flush_ms))
            if settings.tick_persistence_enabled else None
        )

        async def readiness() -> dict[str, bool]:
            checks = await redis_check(redis_client)()
            try:
                await pool.fetchval("SELECT 1")
                checks["database"] = True
            except (asyncpg.PostgresError, OSError):
                logger.error("readiness: database check failed", exc_info=True)
                checks["database"] = False
            return checks

        app = create_app(registry=metrics.registry, readiness=readiness)
        server = _Server(uvicorn.Config(app, host="127.0.0.1", port=settings.http_port,
                                        log_level="warning", lifespan="off"))
        server_task = asyncio.create_task(server.serve())

        pipeline = MarketDataPipeline(
            provider=provider,
            normalizer=TickNormalizer(settings.watchlist),
            deduper=LruDeduper(100_000),
            builders=[CandleBuilder(tf, calendar) for tf in Timeframe],
            store=PostgresCandleStore(pool),
            metrics=metrics,
            clock=_utcnow,
            publisher=RedisPublisher(redis_client, metrics, ticks_maxlen=settings.ticks_maxlen,
                                     candles_maxlen=settings.candles_maxlen),
            tick_writer=tick_writer,
            open_candle_throttle=OpenCandleThrottle(
                timedelta(seconds=settings.open_candle_interval_seconds)),
            liveness=LivenessConfig(
                threshold=timedelta(seconds=settings.stale_threshold_seconds),
                in_regular_session=lambda t: calendar.session_for(t) is not None,
            ),
        )

        _install_signal_handlers(stop_event, pipeline)
        pipeline_task = asyncio.create_task(pipeline.run())
        stop_task = asyncio.create_task(stop_event.wait())
        done, _ = await asyncio.wait({pipeline_task, stop_task},
                                     return_when=asyncio.FIRST_COMPLETED)
        if pipeline_task in done and pipeline_task.exception() is not None:
            logger.error("pipeline failed; service stopping",
                         extra={"event": "service_failed"})
            exit_code = EXIT_FAILED
        elif pipeline_task in done:
            logger.info("provider stream finished; serving endpoints until stopped",
                        extra={"event": "stream_finished"})
            await stop_task
        stop_task.cancel()

        if not pipeline_task.done():
            pipeline.request_stop()
            try:
                await asyncio.wait_for(pipeline_task, timeout=settings.shutdown_timeout_seconds)
            except TimeoutError:
                logger.error("shutdown timed out; state not fully flushed",
                             extra={"event": "shutdown_timeout",
                                    "timeout_s": settings.shutdown_timeout_seconds})
                pipeline_task.cancel()
                exit_code = EXIT_FAILED
            except Exception:
                logger.error("pipeline failed during shutdown", exc_info=True)
                exit_code = EXIT_FAILED
        if pipeline_task.done() and not pipeline_task.cancelled() \
                and pipeline_task.exception() is not None:
            exit_code = EXIT_FAILED
    finally:
        if server is not None:
            server.should_exit = True
        if server_task is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(server_task, timeout=5)
        await pool.close()
        await redis_client.aclose()
    logger.info("service stopped", extra={"event": "service_stop", "exit_code": exit_code})
    return exit_code


def _allow_test(env: dict[str, str]) -> bool:
    return env.get("ALLOW_TEST_CALENDAR", "").strip().lower() in {"1", "true", "yes"}


def _install_signal_handlers(stop_event: asyncio.Event, pipeline: MarketDataPipeline) -> None:
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        logger.info("stop signal received", extra={"event": "stop_signal"})
        stop_event.set()
        pipeline.request_stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            # Windows: fall back to KeyboardInterrupt handling in main(). See module docstring.
            logger.warning("signal handlers unavailable on this platform",
                           extra={"event": "no_signal_handlers"})
            return


def serve_main(settings: Settings, env: dict[str, str]) -> int:
    try:
        return asyncio.run(run_service(settings, env))
    except KeyboardInterrupt:
        logger.error("interrupted without graceful flush", extra={"event": "interrupted"})
        return EXIT_INTERRUPTED

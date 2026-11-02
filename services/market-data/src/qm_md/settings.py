"""Runtime configuration from environment variables. Fails fast with a precise message."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigurationError

_TRUE = frozenset({"1", "true", "yes", "on"})


def _flag(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in _TRUE


def _number(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number, got {raw!r}") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    provider: str
    watchlist: tuple[str, ...]
    calendar_path: Path
    fixture_dir: Path
    replay_speed: float
    redis_url: str
    database_url: str
    http_port: int
    tick_persistence_enabled: bool
    tick_licence_confirmed: bool
    tick_batch_size: int
    tick_flush_ms: int
    stale_threshold_seconds: float
    shutdown_timeout_seconds: float
    open_candle_interval_seconds: float
    ticks_maxlen: int
    candles_maxlen: int
    log_level: str


REQUIRED = ("MARKET_DATA_WATCHLIST", "TRADING_CALENDAR_FILE", "REDIS_URL", "DATABASE_URL")


def load_settings(env: Mapping[str, str]) -> Settings:
    missing = [name for name in REQUIRED if not env.get(name, "").strip()]
    if missing:
        raise ConfigurationError(f"missing required environment variables: {', '.join(missing)}")

    persistence = _flag(env, "TICK_PERSISTENCE_ENABLED", default=False)
    licence = _flag(env, "TICK_LICENCE_CONFIRMED", default=False)
    if persistence and not licence:
        raise ConfigurationError(
            "TICK_PERSISTENCE_ENABLED=true requires TICK_LICENCE_CONFIRMED=true. Confirm the "
            "provider licence in docs/DATA_PROVIDER.md first."
        )

    watchlist = tuple(s.strip() for s in env["MARKET_DATA_WATCHLIST"].split(",") if s.strip())
    if not watchlist:
        raise ConfigurationError("MARKET_DATA_WATCHLIST contains no symbols")

    port = int(_number(env, "MARKET_DATA_HTTP_PORT", 8001))
    if not 1 <= port <= 65535:
        raise ConfigurationError(f"MARKET_DATA_HTTP_PORT out of range: {port}")

    batch = int(_number(env, "TICK_BATCH_SIZE", 500))
    if batch < 1:
        raise ConfigurationError("TICK_BATCH_SIZE must be at least 1")

    return Settings(
        provider=env.get("MARKET_DATA_PROVIDER", "REPLAY").strip().upper(),
        watchlist=watchlist,
        calendar_path=Path(env["TRADING_CALENDAR_FILE"]),
        fixture_dir=Path(env.get("REPLAY_FIXTURE_DIR", "./fixtures")),
        replay_speed=_number(env, "REPLAY_SPEED", 0.0),
        redis_url=env["REDIS_URL"].strip(),
        database_url=env["DATABASE_URL"].strip(),
        http_port=port,
        tick_persistence_enabled=persistence,
        tick_licence_confirmed=licence,
        tick_batch_size=batch,
        tick_flush_ms=int(_number(env, "TICK_FLUSH_MS", 500)),
        stale_threshold_seconds=_number(env, "STALE_DATA_THRESHOLD_SECONDS", 15),
        shutdown_timeout_seconds=_number(env, "SHUTDOWN_TIMEOUT_SECONDS", 10),
        open_candle_interval_seconds=_number(env, "OPEN_CANDLE_INTERVAL_SECONDS", 1.0),
        ticks_maxlen=int(_number(env, "TICKS_STREAM_MAXLEN", 100_000)),
        candles_maxlen=int(_number(env, "CANDLES_STREAM_MAXLEN", 10_000)),
        log_level=env.get("LOG_LEVEL", "INFO").strip().upper(),
    )

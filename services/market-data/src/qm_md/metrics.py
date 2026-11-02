"""Prometheus metrics. Each service owns a registry so tests can inspect values in isolation."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge


class MarketDataMetrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry if registry is not None else CollectorRegistry()
        self.ticks_received = Counter(
            "ticks_received_total", "Raw ticks received from the provider", registry=self.registry
        )
        self.ticks_rejected = Counter(
            "ticks_rejected_total",
            "Ticks rejected, by reason. A tick rejected by several builders counts once "
            "per reason.",
            ["reason"],
            registry=self.registry,
        )
        self.last_tick_age = Gauge(
            "last_tick_age_seconds",
            "Seconds between the clock and the ingest time of the last accepted tick",
            registry=self.registry,
        )
        self.candles_emitted = Counter(
            "candles_emitted_total",
            "Final candles emitted, by timeframe",
            ["tf"],
            registry=self.registry,
        )
        self.candle_gaps = Counter(
            "candle_gaps_total", "Intraday bars with no ticks, by timeframe", ["tf"],
            registry=self.registry,
        )
        self.reconnects = Counter(
            "reconnects_total", "Provider reconnect attempts", registry=self.registry
        )
        self.redis_publish_errors = Counter(
            "redis_publish_errors_total",
            "Failed Redis Stream writes, by stream",
            ["stream"],
            registry=self.registry,
        )
        self.store_errors = Counter(
            "store_errors_total", "Failed candle persistence operations", registry=self.registry
        )

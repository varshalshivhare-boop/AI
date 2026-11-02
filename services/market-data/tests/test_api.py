from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry

from qm_md.api import create_app
from qm_md.metrics import MarketDataMetrics


async def ready_ok() -> dict[str, bool]:
    return {"redis": True}


async def ready_down() -> dict[str, bool]:
    return {"redis": False}


def test_liveness_does_not_depend_on_dependencies() -> None:
    client = TestClient(create_app(registry=CollectorRegistry(), readiness=ready_down))
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


def test_readiness_reflects_dependencies() -> None:
    ok = TestClient(create_app(registry=CollectorRegistry(), readiness=ready_ok))
    assert ok.get("/ready").status_code == 200
    down = TestClient(create_app(registry=CollectorRegistry(), readiness=ready_down))
    r = down.get("/ready")
    assert r.status_code == 503
    assert r.json() == {"ready": False, "checks": {"redis": False}}


def test_metrics_exposes_the_required_series() -> None:
    m = MarketDataMetrics()
    m.ticks_received.inc()
    m.ticks_rejected.labels(reason="DUPLICATE").inc()
    m.candles_emitted.labels(tf="1m").inc()
    m.redis_publish_errors.labels(stream="ticks.normalized").inc()
    client = TestClient(create_app(registry=m.registry, readiness=ready_ok))
    body = client.get("/metrics").text
    for name in ("ticks_received_total", "ticks_rejected_total", "last_tick_age_seconds",
                 "candles_emitted_total", "reconnects_total", "redis_publish_errors_total"):
        assert name in body, name
    assert 'ticks_rejected_total{reason="DUPLICATE"} 1.0' in body

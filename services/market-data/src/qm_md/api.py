"""Health, readiness and metrics endpoints. Liveness never checks dependencies. Readiness does."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from redis.exceptions import RedisError

logger = logging.getLogger("qm_md.api")

Readiness = Callable[[], Awaitable[dict[str, bool]]]


def create_app(*, registry: CollectorRegistry, readiness: Readiness) -> FastAPI:
    app = FastAPI(title="qm-market-data", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/ready")
    async def ready() -> JSONResponse:
        checks = await readiness()
        ok = all(checks.values())
        return JSONResponse(status_code=200 if ok else 503,
                            content={"ready": ok, "checks": checks})

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return app


def redis_check(client: object) -> Readiness:
    """Readiness probe that pings Redis. Failures are logged, then reported as not ready."""

    async def check() -> dict[str, bool]:
        ping = getattr(client, "ping")  # noqa: B009 - client type is loose on purpose
        try:
            await ping()
        except (RedisError, OSError):
            logger.error("readiness: redis ping failed", exc_info=True)
            return {"redis": False}
        return {"redis": True}

    return check

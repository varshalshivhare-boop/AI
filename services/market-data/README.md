# market-data (PC 1)

Owner: PC 1 (Python, data platform). Phase 1 implementation.

## What works

| Milestone | Status | Evidence |
|---|---|---|
| 1.1 Provider interface, ReplayProvider | Done | `tests/test_replay.py` |
| 1.2 Upstox adapter | **Scaffold only.** Config and refusal to run without credentials work. No decoder. | `tests/test_upstox.py` |
| 1.3 Normalization, dedupe, ordering policy | Done | `tests/test_normalize.py`, `tests/test_dedupe.py` |
| 1.4 Session calendar | Done. Real holiday data is **not** loaded (placeholder refused). | `tests/test_sessions.py` |
| 1.5 Candle builder | Done. Gaps are recorded but not emitted as candles (see Open questions). | `tests/test_candles.py`, `tests/test_golden.py` |
| 1.6 Persistence and streaming | Redis and PostgreSQL paths done. Tick persistence **not** implemented. | `tests/test_redis_pipeline.py`, `tests/test_store_postgres.py` |
| 1.7 Observability | Endpoints and metrics done. Dashboard committed. No long-running server entry point yet. | `tests/test_api.py`, `infra/grafana/dashboards/market-data.json` |

Stale-data detection (`stale.py`) and the reconnect loop (`providers/reconnect.py`) are implemented and tested in isolation. They are not wired into a live provider because none exists yet.

## Phase 2 status

| Milestone | Status | Evidence |
|---|---|---|
| 2.1 Compression on candles | Migration written (`migrations/0002`). **Not verified**: needs real TimescaleDB. | none yet |
| 2.2 Tick persistence behind flag | Done. Off by default; needs licence flag. | `tests/test_phase2_ticks_pg.py`, `tests/test_phase2_settings.py` |
| 2.3 Open-candle channel | Done. New contract `candle.open.v1.json` (for review). | `tests/test_phase2_open_candles.py` |
| 2.4 Stale and recovery in live loop | Done for DEGRADED and CONNECTED. **Reconnect loop not yet wired into `serve`**: a provider failure stops the process with exit 1. | `tests/test_phase2_liveness.py` |
| 2.5 Graceful shutdown | Done on Linux and Docker. **Windows Ctrl+C does not flush** (asyncio has no signal handlers there). | `tests/test_phase2_shutdown.py`, manual `serve` check |
| 2.6 Single entry point | Done. `python -m qm_md serve`. Keeps serving after the stream ends until stopped. | manual check, see below |
| 2.7 Consumer contract | Done. | `tests/test_phase2_consumer.py` |

## Run the service

```bash
python -m qm_md serve        # reads .env values from the environment
# health: curl localhost:$MARKET_DATA_HTTP_PORT/health
# stop:   SIGTERM (Linux) -> flush -> exit 0
```

## Setup

```bash
cd services/market-data
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Run the tests

```bash
# Unit and offline tests (no services needed)
pytest

# Integration tests: start Redis (redis-server on PATH) and a database with migration 0001
TEST_DATABASE_URL=postgresql://quantmind:<password>@localhost:5432/md_test pytest

# Coverage on the modules with the 90% acceptance threshold
pytest --cov=qm_md.candles --cov=qm_md.normalize --cov-report=term-missing

# Lint and types
ruff check src tests
mypy            # strict, covers src/
```

## Replay a fixture day

```bash
python -m qm_md replay \
  --calendar calendars/nse_holidays_TEST_ONLY.yaml --allow-test-calendar \
  --symbols RELIANCE --date 2026-10-19 --speed 0 \
  --redis-url redis://localhost:6379/0 \
  --database-url postgresql://quantmind:<password>@localhost:5432/quantmind \
  --output-dir /tmp/replay_out
```

Omit `--redis-url` or `--database-url` to run without them. Without a database, candles are kept in memory only and a warning is logged.

`--allow-test-calendar` is required because the only calendar in the repository for the 2026-10-19 week is a TEST file. It lists no holidays, and that is an assumption that has not been verified.

## Regenerate expected outputs

```bash
python tests/regenerate_golden.py
```

Only do this after a deliberate, reviewed change to candle rules. Review the diff. The independent oracle in `tests/test_golden.py` must still pass.

## Layout

```
src/qm_md/
  models.py        domain types; Pydantic v2, frozen
  sessions.py      NSE regular session and holiday file loader
  normalize.py     validation and reason codes
  dedupe.py        bounded LRU duplicate window
  candles.py       session-aligned OHLCV builder, sealing, gaps
  contracts.py     payload mapping to packages/contracts v1 schemas
  publish.py       Redis Streams publisher (non-fatal on failure)
  store.py         idempotent PostgreSQL upsert; in-memory store for tests
  pipeline.py      orchestration and failure policy
  providers/       base, replay, upstox (scaffold), reconnect loop
  api.py           /health, /ready, /metrics (FastAPI)
  cli.py           replay command
tests/             unit, golden, oracle, and integration tests
calendars/         TEST calendar; placeholder calendar lives at the repo level
```

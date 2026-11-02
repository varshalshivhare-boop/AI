# Architecture

## Purpose

QuantMind AI produces explainable BUY, SELL and NO_TRADE decisions for NSE cash equities, for research and paper trading. It does not place orders with any broker.

## Services and boundaries

| Component | Language | Owner | Role |
|---|---|---|---|
| `services/market-data` | Python | PC 1 | Provider adapters, normalization, candle building, persistence, health |
| `services/quant-engine` | Python | PC 2 | Indicators, structure, regime, strategies, risk, backtest, paper trading, ML |
| `apps/api` | TypeScript (NestJS) | PC 3 | Auth, REST, WebSocket gateway, alerts |
| `apps/web` | TypeScript (Next.js) | PC 3 | Research terminal UI |
| `packages/contracts` | JSON Schema | All, reviewed | Versioned message and API shapes |
| `migrations` | SQL | PC 1 | Database schema, forward-only |
| `infra` | YAML, config | PC 1 | Compose, Prometheus, Grafana |

Services communicate only through three channels: the PostgreSQL/TimescaleDB database, Redis Streams, and the REST and WebSocket API. No service imports code from another service.

## Data flow: tick to alert

```
Provider WebSocket
   -> market-data: decode, normalize, validate, dedupe   [tick.normalized.v1]
   -> Redis ticks.normalized
   -> market-data: candle builder (session-aligned)
   -> candles table (closed bars only) + Redis candles.closed.<tf>  [candle.closed.v1]
   -> quant-engine: indicators, structure, volume, order flow, regime
   -> quant-engine: strategies -> risk engine (may reject) -> signal
   -> signals table + Redis signals.generated                     [signal.generated.v1]
   -> api gateway: subscription filtering, backpressure, fan-out to WebSocket clients
   -> alert service: dedupe, expiry, LIVE-only Telegram send
   -> dashboard
```

## Non-negotiable rules

1. `provider_ts` and `ingest_ts` are stored separately everywhere. Wall-clock time is never used as provider time.
2. Every record carries `data_mode` (`LIVE`, `REPLAY`, `DEMO`, `HISTORICAL`). Only `LIVE` may trigger an alert.
3. Prices are `NUMERIC` in the database and decimal strings on the wire. Never floats.
4. Signals are computed on bar close and modelled as executed on the next bar. No future bars are used.
5. NO_TRADE is a valid outcome. Incomplete or stale input yields NO_TRADE with `DATA_INSUFFICIENT` or `DATA_STALE`, never BUY or SELL.
6. Probabilities are shown only when `calibrated` is true.

## Version pinning

Images are pinned in `infra/docker-compose.yml`:
- `timescale/timescaledb:2.17.2-pg16`
- `redis:7.2.5-alpine`
- `prom/prometheus:v2.54.1`
- `grafana/grafana:11.2.0`

Before the first `docker compose pull`, confirm each tag exists on its registry. Bump tags in a dedicated PR.

## Deliberately excluded from the MVP

Kafka, Kubernetes, separate ML serving, deep learning, and any real-money order routing.

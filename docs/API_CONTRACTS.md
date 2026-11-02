# API Contracts

Owned by PC 3. This document lists the surface the dashboard needs. Endpoints are added here before they are implemented.

## Conventions

- Base path `/api/v1`. Auth with `Authorization: Bearer <access_token>`.
- Every data response includes `data_mode` and `source_ts`. Where relevant, also `ingest_ts`.
- Errors use one envelope: `{ "error": { "code": "...", "message": "...", "request_id": "..." } }`. Raw database errors are never returned.
- Lists are paginated with `limit` (max 200) and `cursor`.
- Decimal values are strings.

## REST (planned)

| Method | Path | Purpose | Role |
|---|---|---|---|
| POST | `/auth/login` | Issue access and refresh tokens | public, rate-limited |
| POST | `/auth/refresh` | Rotate tokens | any |
| GET | `/instruments` | Watchlist and instrument metadata | USER |
| GET | `/candles` | `symbol`, `timeframe`, `from`, `to` | USER |
| GET | `/signals` | Active and historical signals, paginated | USER |
| GET | `/signals/:id` | Signal with full evidence | USER |
| GET | `/strategies` | Strategy list with enabled state | USER |
| PATCH | `/strategies/:name` | Enable or disable, change config | ADMIN |
| POST | `/backtests` | Create a QUEUED backtest job. Does not run it. | USER |
| GET | `/backtests/:jobId` | Job status and result reference | USER |
| GET | `/paper/positions` | Open simulated positions | USER |
| GET | `/paper/trades` | Simulated trade history | USER |
| GET | `/market/status` | Session state and calendar | USER |
| GET | `/health` | Liveness | public |
| GET | `/health/ready` | Database and Redis reachable | internal |

## WebSocket (planned)

Endpoint `/ws`, authenticated during the handshake. The client sends `subscribe` and `unsubscribe` messages filtered by `symbol` and `timeframe`. The server sends `candle`, `signal`, `provider_health` and `heartbeat` messages, each with `data_mode`. If no update arrives within `WS_STALE_WARNING_SECONDS`, the server sends a `stale` warning.

## Contract source of truth

Message payloads are defined in `packages/contracts`. REST DTOs are generated from the same schemas where a schema exists. This document describes intent. The schemas and OpenAPI output are authoritative.

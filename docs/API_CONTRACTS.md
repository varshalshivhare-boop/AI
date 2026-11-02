# QuantMind AI — API Contracts

All endpoints return uniform response envelope:
```json
{
  "data": { ... },
  "data_mode": "LIVE" | "REPLAY" | "DEMO",
  "source_ts": "ISO-8601",
  "ingest_ts": "ISO-8601",
  "request_id": "UUID"
}
```

## REST Endpoints
- `GET /health` -> `{ status: "ok", data_mode: "DEMO" | "LIVE", providers: { redis: true, db: true } }`
- `POST /auth/login` -> `{ access_token, refresh_token, user: { id, email, role } }`
- `POST /auth/refresh` -> `{ access_token, refresh_token }`
- `GET /instruments` -> List of active NSE instruments
- `GET /candles?symbol=NIFTY50&timeframe=5m&limit=200` -> Candles array
- `GET /signals?symbol=NIFTY50&limit=50` -> Historical and active signals
- `POST /backtests` -> Enqueue backtest job, returns `{ id, status: "QUEUED" }`
- `GET /backtests/:id` -> Poll status or get full in-sample / out-of-sample metrics
- `GET /paper-trading/positions` -> Virtual capital, open positions, unrealized P&L
- `GET /paper-trading/trades` -> Executed paper trade log
- `POST /paper-trading/orders` -> Execute paper entry or exit
- `GET /system/monitoring` -> Real-time system telemetry and feed health

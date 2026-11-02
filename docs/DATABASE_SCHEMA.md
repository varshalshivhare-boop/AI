# Database Schema

Migration `0001_init.sql` creates `instruments`, `candles` and `signals`. Migrations are recorded in `schema_migrations` with a SHA-256 checksum. An applied migration that is later edited causes the runner to fail. Write a new migration instead.

## Conventions

- Timestamps: `TIMESTAMPTZ`, stored in UTC.
- Prices: `NUMERIC(14,4)`. Volumes: `BIGINT`.
- Every table has `schema_version SMALLINT NOT NULL DEFAULT 1`.
- `data_mode` is constrained to `LIVE | REPLAY | DEMO | HISTORICAL`.
- Enumerations are `TEXT` with `CHECK` constraints, so adding a value is a migration, not a type change.

## instruments

| Column | Type | Notes |
|---|---|---|
| instrument_id | BIGSERIAL PK | |
| exchange, segment, symbol | TEXT, unique together | Only `NSE` and `CASH_EQUITY` allowed in v1 |
| isin | TEXT | Format-checked when present |
| tick_size, lot_size | NUMERIC, INT | Used by the risk engine |
| is_active | BOOLEAN | Watchlist removal sets false, never deletes |

## candles

- Primary key `(instrument_id, timeframe, ts)`. The key includes `ts`, which TimescaleDB requires for a hypertable's unique constraints.
- Hypertable on `ts`, 7-day chunks.
- CHECKs: `high >= low`, `high >= open and close`, `low <= open and close`, all prices > 0, `volume >= 0`, `NOT is_missing OR volume = 0`.
- `is_final` distinguishes closed bars from open ones. Only closed bars are persisted by the pipeline.
- `is_missing` marks gaps. Gap bars carry no interpolated prices.

Expected volume: about 1,875 bars per symbol per 5 sessions at 1m. The 1m table grows linearly with the watchlist. Compress chunks older than 30 days in a later migration.

## signals

- `action` in `BUY | SELL | NO_TRADE`.
- CHECK `signals_trade_plan_complete`: BUY and SELL must have entry zone, stop and target 1, with `entry_low <= entry_high`.
- CHECK `signals_no_trade_reason`: NO_TRADE must have `reason_code`.
- CHECK `signals_calibrated_requires_probability`: a calibrated signal must carry a probability.
- `status` follows GENERATED, DELIVERED, INVALIDATED, EXPIRED, CLOSED. Transitions are enforced in the application and logged.
- `evidence` and `invalidation_conditions` are JSONB, mirroring the contract.

## Tables planned for later migrations

Owned by the phase that introduces them: `backtest_runs`, `backtest_jobs`, `simulated_trades` (PC 2), `model_versions` (PC 2), `signal_evidence` (PC 2), `alert_history` (PC 3), `users` and `refresh_tokens` (PC 3), `system_health` (PC 1), `market_regimes` (PC 2), `strategy_configs` (PC 2).

Raw ticks are not in the schema. Tick persistence is an optional table decided in Milestone 1.6 after the licence review in `DATA_PROVIDER.md`.

# Market Data Provider

## Provider interface

`MarketDataProvider` exposes `connect`, `disconnect`, `subscribe`, `unsubscribe`, `stream` (yields normalized ticks) and `health`. Every provider emits `tick.normalized.v1` and sets `data_mode`.

## Providers

| Provider | Mode | Status in Phase 0 |
|---|---|---|
| `ReplayProvider` | `REPLAY` | Specified. Reads `fixtures/`. Implemented in Milestone 1.1 |
| `UpstoxProvider` | `LIVE` | Specified. Adapter starts in Milestone 1.2, after verifying the current official Upstox Market Data Feed V3 documentation |

The Upstox adapter must not be written from memory. Message formats, the Protobuf schema, authentication and rate limits are taken from the official documentation at the time of implementation, and the documentation version is recorded in the adapter's README.

## Credentials

Credentials come only from environment variables (see `.env.example`). If `MARKET_DATA_PROVIDER=UPSTOX` and credentials are missing, the service exits at startup with `ConfigurationError`. It never falls back to replay data while claiming to be live.

## Timestamps

- `provider_ts`: time reported by the provider. If the provider does not supply one for a message, that message is flagged and not used for session logic.
- `ingest_ts`: time this service received the message.
- Bar boundaries use `provider_ts`. Latency is `ingest_ts - provider_ts`, exposed as a metric.

## Staleness and reconnects

- During a regular session, no tick for `STALE_DATA_THRESHOLD_SECONDS` moves the provider to `DEGRADED` and publishes `provider.health`. Signals are blocked until the feed recovers.
- Reconnects use exponential backoff with jitter, capped at `PROVIDER_RECONNECT_MAX_BACKOFF_SECONDS`, and resubscribe to the watchlist.

## Tick persistence: status (Phase 2)

- Implemented: `ticks` table (migration 0003, 7-day retention policy), batched writer (`ticks.py`), flag-gated startup.
- To enable, BOTH `TICK_PERSISTENCE_ENABLED=true` AND `TICK_LICENCE_CONFIRMED=true` are required. The service refuses to start with only the first.
- Licence confirmation record (fill in before enabling anywhere):
  - Confirmed by: ______________________ (owner: TODO, business decision)
  - Date: ______________________
  - Provider terms reference: ______________________
- Limitation: ticks without a provider sequence are refused (`ValueError`). The `ticks` primary key includes `provider_sequence`. Confirm that the Upstox feed supplies one before enabling live persistence.

## Tick persistence: status and implications (Phase 1 notes)

Status (Milestone 1.6):

- Normalized ticks are published to the `ticks.normalized` Redis Stream with approximate MAXLEN trimming (`TICKS_STREAM_MAXLEN`). This is the only tick sink implemented.
- Raw ticks are **not** written to TimescaleDB. The `TICK_PERSISTENCE_ENABLED` variable in `.env.example` has no effect yet: no tick writer exists, and the flag is reserved until the licence questions below are answered.
- Retention for the Redis stream is by length only (MAXLEN), not by time. Redis is not a store of record.

Implications when persistence is added:

- Volume: a 500-symbol watchlist at roughly 1 tick per second per symbol during a 375-minute session is on the order of 10^8 rows per year. Compression and a retention policy are required before enabling it.
- Licence: storing raw ticks may be restricted by the provider's terms, independently of displaying them.
- Retention must be set explicitly (`TICK_RETENTION_DAYS`) and enforced with a TimescaleDB retention policy in a migration, not by a cron job.

## Licensing, retention and terms

Before enabling tick persistence (`TICK_PERSISTENCE_ENABLED`), confirm all of the following against the provider's current terms:

1. Whether storing raw ticks is permitted, and for how long.
2. Whether redistribution is permitted. Dashboard users seeing live prices may be a separate permission from storing data.
3. Whether the data may be used for backtesting, and whether it may be shown to other users.
4. Exchange data rules that apply to the account holder.

Until these are answered in writing, only candles derived from the feed are stored, and tick storage stays off. This is a product decision for the team and is not a legal opinion. Confirm with counsel or the provider.

## Calendar

Sessions come from `services/market-data/calendars/nse_holidays.yaml`. The file is currently an unpopulated placeholder and the loader must refuse it. Weekends are closed. Pre-open and regular sessions are modelled separately.

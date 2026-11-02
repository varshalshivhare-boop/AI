# Fixtures

**Every file in this directory is SYNTHETIC or a labelled historical sample. None of it is live market data.**

## Contents

| File | Symbols | Sessions | Bars | Source |
|---|---|---|---|---|
| `SYNTHETIC_RELIANCE_1m_2026-10-19_2026-10-23.csv` | RELIANCE | 5 | 1,875 | Generated |
| `SYNTHETIC_HDFCBANK_1m_2026-10-19_2026-10-23.csv` | HDFCBANK | 5 | 1,875 | Generated |
| `SYNTHETIC_INFY_1m_2026-10-19_2026-10-23.csv` | INFY | 5 | 1,875 | Generated |
| `SHA256SUMS` | | | | Checksums of the three files above |

## Columns

`data_source, symbol, exchange, session_date, bar_start_utc, open, high, low, close, volume`

- `data_source` is always `SYNTHETIC` in these files. Consumers must not label this data as `LIVE`. Replay consumers set `data_mode=REPLAY`.
- `bar_start_utc` is the bar start in UTC. The session runs 09:15 to 15:29 IST, which is 03:45 to 09:59 UTC.
- Prices are INR with two decimals and an NSE tick size of 0.05.

## How they were made

`scripts/generate_fixtures.py` produces them from a fixed seed. Running it again gives byte-identical files, which the `SHA256SUMS` file confirms.

```bash
python3 scripts/generate_fixtures.py
sha256sum -c fixtures/SHA256SUMS   # run from inside fixtures/
```

## What they are for

- Unit and integration tests in all three services.
- Replay mode for the market-data service (`MARKET_DATA_PROVIDER=REPLAY`).
- Demo data for the mock server (labelled `DEMO` in the UI).

## What they are NOT for

- Measuring strategy performance. The price process is a random walk, so every pattern in it is noise. Any backtest on this data tests the engine's code, not a trading edge.
- Calibrating probabilities or training ML models.
- Claiming historical results.

Real historical data will be added later under `fixtures/historical/`, with the provider and licence recorded alongside each file.

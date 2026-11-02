# Contracts

Versioned JSON Schemas shared by all services. v1 files are frozen. See `STREAMS.md` for the stream mapping.

| Schema | Producer | Consumers |
|---|---|---|
| `tick.normalized.v1.json` | PC 1 | PC 3 gateway |
| `candle.closed.v1.json` | PC 1 | PC 2, PC 3 |
| `signal.generated.v1.json` | PC 2 | PC 3 |
| `backtest_job.v1.json` | PC 3 | PC 2 |
| `provider_health.v1.json` | PC 1 | PC 3 |

Validate with `python3 scripts/validate_schemas.py`.

Changes: open a PR tagged `contract-change`. All three PCs must approve. Adding a field to a v1 file is not allowed; create `vN+1` instead. Generated TypeScript (PC 3) and Pydantic (PC 1, PC 2) models are produced from these files, not written by hand.

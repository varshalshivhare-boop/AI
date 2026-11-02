# QuantMind AI

Quantitative market-intelligence and paper-trading platform for NSE cash equities.

It produces explainable BUY, SELL and NO_TRADE decisions for research and paper trading. **It does not place real orders, guarantee returns, or claim prediction accuracy.** Performance is measured by backtesting and out-of-sample validation.

## Repository layout

```
services/market-data     PC 1  Python   provider adapters, candles, persistence
services/quant-engine    PC 2  Python   indicators, strategies, risk, backtest, ML
apps/api                 PC 3  NestJS   REST, WebSocket gateway, alerts
apps/web                 PC 3  Next.js  research terminal
packages/contracts       shared JSON Schemas (v1 frozen, reviewed by all)
migrations               PC 1  SQL, forward-only, checksummed
infra                    PC 1  docker-compose, Prometheus, Grafana
fixtures                 SYNTHETIC or labelled sample data only
docs                     architecture, schema, API, provider, plan
scripts                  migrate, validate schemas, fixtures, verify
```

## Three-PC ownership rules

The project is built by three developers on three machines. These rules keep them from blocking each other.

1. **Edit only the folders you own.** PC 1 owns `services/market-data`, `migrations`, `infra`. PC 2 owns `services/quant-engine`. PC 3 owns `apps/` and generates TypeScript types.
2. **Contracts are shared.** Changes under `packages/contracts` need a PR tagged `contract-change` and approval from all three PCs.
3. **Schemas are frozen once published.** Add `vN+1` files. Do not edit `v1` files.
4. **Migrations are forward-only.** Add a new numbered file. Editing an applied migration fails the runner by design.
5. **Every service runs on fixtures.** No PC needs another PC's running service to pass its tests.
6. **Shared data is labelled.** Every record carries `data_mode`. Only `LIVE` may trigger an alert. Fixture and replay output is never presented as live.

## Prerequisites

- Docker Desktop or Docker Engine with Compose v2.20+
- Python 3.12 (for the validation scripts)
- `psql` client (only for running the CI-equivalent migration check outside Docker)
- Node.js 20+ (from Phase 8 onward)

## First-time setup

```bash
cp .env.example .env
# Edit .env. At minimum set POSTGRES_PASSWORD and GRAFANA_ADMIN_PASSWORD (if using observability),
# and replace the JWT placeholders with: openssl rand -hex 64
```

## Start the stack

```bash
docker compose up -d                                   # TimescaleDB and Redis
docker compose ps                                      # both should show "healthy"
docker compose --profile observability up -d           # optional: Prometheus and Grafana
```

## Apply migrations

```bash
./scripts/migrate.sh      # first run applies 0001_init
./scripts/migrate.sh      # second run: "skip 0001_init", no changes
```

## Verify Phase 0

```bash
./scripts/verify.sh               # schemas, fixtures, migration
SKIP_DB=1 ./scripts/verify.sh     # without a running database
```

## Stop and reset

```bash
docker compose down               # stop, keep data
docker compose down -v            # stop and delete all data (local only)
```

## Where to read next

- `docs/ARCHITECTURE.md`: components, data flow, non-negotiable rules
- `docs/IMPLEMENTATION_PLAN.md`: phases and milestones
- `docs/DATABASE_SCHEMA.md`, `docs/API_CONTRACTS.md`, `docs/DATA_PROVIDER.md`
- `packages/contracts/STREAMS.md`: Redis Stream names and consumer groups
- `fixtures/README.md`: what the sample data is and is not

## Financial and data safety

- Research and paper trading only. No code in this repository places broker orders.
- No guaranteed returns. No accuracy claims.
- Fee schedule and trading holidays are unpopulated placeholders. The engine refuses to size trades until they are verified.
- Upstox and Telegram credentials are obtained by you, from your own accounts, and stored only in `.env`.

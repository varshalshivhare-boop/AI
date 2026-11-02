# Implementation Plan

## Phase 0: Skeleton and contracts (complete when `scripts/verify.sh` passes)

- Monorepo layout, ownership rules, docs.
- Docker Compose for TimescaleDB and Redis with health checks. Observability is an opt-in profile.
- Migration 0001 and an idempotent runner.
- Five versioned JSON Schemas with valid examples and negative tests.
- Redis Stream naming contract.
- `.env.example`, deterministic SYNTHETIC fixtures, placeholders for the holiday calendar and fee schedule.

## Phase 1 (PC 1): Provider abstraction, replay, normalization, candles, session calendar

Milestones 1.1 to 1.7 as set out in the PC 1 prompt.

## Phase 2 (PC 1): Persistence and streaming

Redis Streams publishing, idempotent candle upserts, tick persistence decision.

## Phase 3 (PC 2): Indicator library with mathematical tests

Every metric has a formula in `docs/metrics/`, hand-computed test values, property tests, and cross-checks against a reference library.

## Phase 4 (PC 2): Structure, volume, order flow, regime

Interpretable rules only. Output an explicit `UNCERTAIN` when signals conflict.

## Phase 5 (PC 2): Strategies and risk engine

Six strategies, each independently configurable. The risk engine can reject, and rejects when inputs are incomplete or fee schedules are unpopulated.

## Phase 6 (PC 2): Backtester and walk-forward evaluation

Signals on bar close, execution on next bar open. Out-of-sample results are the headline. Runs are reproducible.

## Phase 7 (PC 2): ML pipeline

Only after Phases 3 to 6 pass. A model that does not beat the rule-based baseline out-of-sample is not promoted.

## Phase 8 (PC 3): NestJS API, gateway, auth, alerts

## Phase 9 (PC 3): Next.js dashboard

## Phase 10 (PC 2 paper trading, PC 3 Telegram, joint): Paper trading, Telegram, monitoring, deployment

## Dependencies

Phases 1 to 2 and 3 to 6 run in parallel on fixtures. Phase 7 depends on Phase 6. Phase 8 can run on the mock server. Integration sessions follow the integration-session prompt, one milestone at a time.

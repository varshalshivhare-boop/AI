# QuantMind AI — Architecture & Specifications

## System Topology & Boundaries
QuantMind AI is an NSE intraday research terminal and paper-trading platform.
Execution is restricted to simulation and paper trading only. No real-money broker connections.

### Component Ownership
- `/services/market-data`: Ingests and normalizes live/historic tick and candle feeds (PC 1).
- `/services/quant-engine`: Pure indicator math, price action, volume/order flow heuristics, regimes, strategies, risk engine, and ML scoring (PC 2).
- `/packages/contracts`: Single source of truth JSON schemas and generated TypeScript / Python models.
- `/apps/api`: NestJS API & Real-time WebSocket Gateway for user authentication, strategy management, backtest queuing, and paper trading.
- `/apps/web`: Next.js App Router research terminal with TradingView Lightweight Charts, real-time telemetry, paper trading, and strategy laboratory.

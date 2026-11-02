# QuantMind AI — Database Schema

```sql
-- Instruments
CREATE TABLE instruments (
    symbol VARCHAR(32) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    exchange VARCHAR(16) DEFAULT 'NSE',
    tick_size DECIMAL(10, 2) DEFAULT 0.05,
    lot_size INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE
);

-- Backtest jobs (owned by quant-engine / api)
CREATE TABLE backtest_jobs (
    id UUID PRIMARY KEY,
    symbol VARCHAR(32) NOT NULL,
    strategy VARCHAR(64) NOT NULL,
    timeframe VARCHAR(16) NOT NULL,
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE NOT NULL,
    parameters JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'QUEUED', -- QUEUED, RUNNING, COMPLETED, FAILED
    results JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Simulated Paper Trades
CREATE TABLE simulated_trades (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    strategy VARCHAR(64) NOT NULL,
    timeframe VARCHAR(16) NOT NULL,
    action VARCHAR(16) NOT NULL, -- BUY, SELL
    quantity INT NOT NULL,
    entry_price DECIMAL(12, 2) NOT NULL,
    exit_price DECIMAL(12, 2),
    pnl DECIMAL(12, 2),
    slippage DECIMAL(10, 4) DEFAULT 0.0,
    brokerage_fees DECIMAL(10, 2) DEFAULT 0.0,
    status VARCHAR(16) NOT NULL, -- OPEN, CLOSED
    paper_flag BOOLEAN DEFAULT TRUE NOT NULL, -- ALWAYS TRUE
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE
);

-- Alert History
CREATE TABLE alert_history (
    id UUID PRIMARY KEY,
    signal_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    channel VARCHAR(32) NOT NULL, -- WEBSOCKET, TELEGRAM
    status VARCHAR(32) NOT NULL, -- GENERATED, DELIVERED, INVALIDATED, EXPIRED, CLOSED
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

CREATE TABLE IF NOT EXISTS instruments (
    symbol VARCHAR(32) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    exchange VARCHAR(16) DEFAULT 'NSE',
    tick_size DECIMAL(10, 2) DEFAULT 0.05,
    lot_size INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS candles (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(32) NOT NULL,
    timeframe VARCHAR(16) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open DECIMAL(12, 2) NOT NULL,
    high DECIMAL(12, 2) NOT NULL,
    low DECIMAL(12, 2) NOT NULL,
    close DECIMAL(12, 2) NOT NULL,
    volume BIGINT NOT NULL,
    vwap DECIMAL(12, 2),
    data_mode VARCHAR(16) NOT NULL DEFAULT 'REPLAY',
    UNIQUE (symbol, timeframe, timestamp)
);

CREATE TABLE IF NOT EXISTS backtest_jobs (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(32) NOT NULL,
    strategy VARCHAR(64) NOT NULL,
    timeframe VARCHAR(16) NOT NULL,
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE NOT NULL,
    parameters JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'QUEUED',
    results JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS simulated_trades (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    strategy VARCHAR(64) NOT NULL,
    timeframe VARCHAR(16) NOT NULL,
    action VARCHAR(16) NOT NULL,
    quantity INT NOT NULL,
    entry_price DECIMAL(12, 2) NOT NULL,
    exit_price DECIMAL(12, 2),
    pnl DECIMAL(12, 2),
    slippage DECIMAL(10, 4) DEFAULT 0.0,
    brokerage_fees DECIMAL(10, 2) DEFAULT 0.0,
    status VARCHAR(16) NOT NULL,
    paper_flag BOOLEAN DEFAULT TRUE NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS alert_history (
    id VARCHAR(64) PRIMARY KEY,
    signal_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

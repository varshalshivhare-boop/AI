-- 0001_init.sql
-- Owner: PC 1 (data platform). Additive changes only after this migration is merged.
-- Applies to: PostgreSQL 16 with TimescaleDB 2.17.
-- Rules:
--   * All timestamps are TIMESTAMPTZ and stored in UTC.
--   * All prices are NUMERIC (never FLOAT).
--   * Every table carries schema_version so rows can be read by version.

BEGIN;

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ---------------------------------------------------------------------------
-- instruments
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS instruments (
    instrument_id   BIGSERIAL PRIMARY KEY,
    exchange        TEXT        NOT NULL DEFAULT 'NSE'
                                CHECK (exchange IN ('NSE', 'BSE')),
    segment         TEXT        NOT NULL DEFAULT 'CASH_EQUITY'
                                CHECK (segment IN ('CASH_EQUITY')),
    symbol          TEXT        NOT NULL CHECK (length(symbol) BETWEEN 1 AND 32),
    isin            TEXT        CHECK (isin IS NULL OR isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'),
    tick_size       NUMERIC(12,4) CHECK (tick_size IS NULL OR tick_size > 0),
    lot_size        INTEGER     CHECK (lot_size IS NULL OR lot_size > 0),
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    schema_version  SMALLINT    NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT instruments_exchange_symbol_uq UNIQUE (exchange, segment, symbol)
);

-- ---------------------------------------------------------------------------
-- candles (OHLCV, closed and open candles; is_final distinguishes them)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candles (
    ts              TIMESTAMPTZ   NOT NULL,            -- bar start, UTC
    instrument_id   BIGINT        NOT NULL REFERENCES instruments (instrument_id),
    timeframe       TEXT          NOT NULL
                                  CHECK (timeframe IN ('1m', '5m', '15m', '30m', '1d')),
    open            NUMERIC(14,4) NOT NULL CHECK (open  > 0),
    high            NUMERIC(14,4) NOT NULL CHECK (high  > 0),
    low             NUMERIC(14,4) NOT NULL CHECK (low   > 0),
    close           NUMERIC(14,4) NOT NULL CHECK (close > 0),
    volume          BIGINT        NOT NULL CHECK (volume >= 0),
    tick_count      INTEGER       CHECK (tick_count IS NULL OR tick_count >= 0),
    is_final        BOOLEAN       NOT NULL DEFAULT TRUE,
    is_missing      BOOLEAN       NOT NULL DEFAULT FALSE, -- gap marker, never interpolated
    data_mode       TEXT          NOT NULL
                                  CHECK (data_mode IN ('LIVE', 'REPLAY', 'DEMO', 'HISTORICAL')),
    provider_ts     TIMESTAMPTZ,                          -- provider-reported time, never wall clock
    ingest_ts       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    schema_version  SMALLINT      NOT NULL DEFAULT 1,
    CONSTRAINT candles_pk PRIMARY KEY (instrument_id, timeframe, ts),
    CONSTRAINT candles_high_ge_low       CHECK (high >= low),
    CONSTRAINT candles_high_ge_open      CHECK (high >= open),
    CONSTRAINT candles_high_ge_close     CHECK (high >= close),
    CONSTRAINT candles_low_le_open       CHECK (low  <= open),
    CONSTRAINT candles_low_le_close      CHECK (low  <= close),
    CONSTRAINT candles_missing_no_ohlc   CHECK (NOT is_missing OR volume = 0)
);

-- Hypertable on ts. Chunk interval is set explicitly, not left to the default.
SELECT create_hypertable(
    'candles', 'ts',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS candles_timeframe_ts_idx
    ON candles (timeframe, ts DESC);

-- ---------------------------------------------------------------------------
-- signals (written by PC 2, read by PC 3)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signals (
    signal_id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id          BIGINT        NOT NULL REFERENCES instruments (instrument_id),
    action                 TEXT          NOT NULL CHECK (action IN ('BUY', 'SELL', 'NO_TRADE')),
    strategy               TEXT          NOT NULL CHECK (length(strategy) BETWEEN 1 AND 64),
    timeframe              TEXT          NOT NULL
                                         CHECK (timeframe IN ('1m', '5m', '15m', '30m', '1d')),
    signal_ts              TIMESTAMPTZ   NOT NULL,       -- bar close time that produced the signal
    price                  NUMERIC(14,4) NOT NULL CHECK (price > 0),
    entry_low              NUMERIC(14,4) CHECK (entry_low  IS NULL OR entry_low  > 0),
    entry_high             NUMERIC(14,4) CHECK (entry_high IS NULL OR entry_high > 0),
    stop_loss              NUMERIC(14,4) CHECK (stop_loss  IS NULL OR stop_loss  > 0),
    target_1               NUMERIC(14,4) CHECK (target_1   IS NULL OR target_1   > 0),
    target_2               NUMERIC(14,4) CHECK (target_2   IS NULL OR target_2   > 0),
    risk_reward            NUMERIC(8,3)  CHECK (risk_reward IS NULL OR risk_reward >= 0),
    probability            NUMERIC(6,5)  CHECK (probability IS NULL OR (probability >= 0 AND probability <= 1)),
    calibrated             BOOLEAN       NOT NULL DEFAULT FALSE,
    regime_trend           TEXT          CHECK (regime_trend IN ('TRENDING_UP', 'TRENDING_DOWN', 'RANGING', 'UNCERTAIN')),
    regime_volatility      TEXT          CHECK (regime_volatility IN ('HIGH', 'LOW', 'NORMAL', 'UNCERTAIN')),
    regime_pressure        TEXT          CHECK (regime_pressure IN ('BUYING', 'SELLING', 'NEUTRAL', 'UNCERTAIN')),
    reason_code            TEXT,                          -- required for NO_TRADE
    status                 TEXT          NOT NULL DEFAULT 'GENERATED'
                                         CHECK (status IN ('GENERATED', 'DELIVERED', 'INVALIDATED', 'EXPIRED', 'CLOSED')),
    expires_at             TIMESTAMPTZ   NOT NULL,
    data_mode              TEXT          NOT NULL
                                         CHECK (data_mode IN ('LIVE', 'REPLAY', 'DEMO', 'HISTORICAL')),
    provider_ts            TIMESTAMPTZ,
    ingest_ts              TIMESTAMPTZ   NOT NULL DEFAULT now(),
    evidence               JSONB         NOT NULL DEFAULT '[]'::jsonb,
    invalidation_conditions JSONB        NOT NULL DEFAULT '[]'::jsonb,
    schema_version         SMALLINT      NOT NULL DEFAULT 1,
    created_at             TIMESTAMPTZ   NOT NULL DEFAULT now(),

    -- A BUY or SELL must carry a complete, ordered trade plan.
    CONSTRAINT signals_trade_plan_complete CHECK (
        action = 'NO_TRADE' OR (
            entry_low IS NOT NULL AND entry_high IS NOT NULL AND
            stop_loss IS NOT NULL AND target_1 IS NOT NULL AND
            entry_low <= entry_high
        )
    ),
    -- NO_TRADE must explain itself.
    CONSTRAINT signals_no_trade_reason CHECK (
        action <> 'NO_TRADE' OR reason_code IS NOT NULL
    ),
    -- A probability is only stored as calibrated when the flag says so.
    CONSTRAINT signals_calibrated_requires_probability CHECK (
        NOT calibrated OR probability IS NOT NULL
    ),
    CONSTRAINT signals_expiry_after_signal CHECK (expires_at > signal_ts)
);

CREATE INDEX IF NOT EXISTS signals_instrument_ts_idx
    ON signals (instrument_id, signal_ts DESC);
CREATE INDEX IF NOT EXISTS signals_status_idx
    ON signals (status) WHERE status IN ('GENERATED', 'DELIVERED');

COMMIT;

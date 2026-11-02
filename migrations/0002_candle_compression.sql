-- 0002_candle_compression.sql
-- Owner: PC 1. Enables native compression on the candles hypertable.
--
-- REQUIRES REAL TIMESCALEDB. The sandbox used for development only had a stub extension,
-- so this file has NOT been verified against TimescaleDB. Verify on
-- timescale/timescaledb:2.17.2-pg16 before relying on it (see Milestone 2.1).

BEGIN;

ALTER TABLE candles SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument_id, timeframe',
    timescaledb.compress_orderby   = 'ts'
);

SELECT add_compression_policy('candles', INTERVAL '30 days', if_not_exists => TRUE);

COMMIT;

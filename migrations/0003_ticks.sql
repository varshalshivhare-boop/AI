-- 0003_ticks.sql
-- Owner: PC 1. Raw tick storage. Written only when TICK_PERSISTENCE_ENABLED=true AND
-- TICK_LICENCE_CONFIRMED=true (enforced in settings.py). The table exists in all environments
-- so schema drift cannot appear between them.
--
-- Retention: the policy below is 7 days, which matches the default TICK_RETENTION_DAYS.
-- SQL cannot read environment variables. To change retention, run:
--   SELECT alter_job(job_id, config => jsonb_set(config, '{drop_after}', '"<n> days"'))
--   FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention' AND hypertable_name = 'ticks';
-- and record the change in docs/DATA_PROVIDER.md.

BEGIN;

CREATE TABLE IF NOT EXISTS ticks (
    provider_ts       TIMESTAMPTZ   NOT NULL,
    instrument_id     BIGINT        NOT NULL REFERENCES instruments (instrument_id),
    ingest_ts         TIMESTAMPTZ   NOT NULL,
    price             NUMERIC(14,4) NOT NULL CHECK (price > 0),
    quantity          BIGINT        NOT NULL CHECK (quantity >= 0),
    provider_sequence BIGINT        NOT NULL,
    data_mode         TEXT          NOT NULL
                                    CHECK (data_mode IN ('LIVE', 'REPLAY', 'DEMO', 'HISTORICAL')),
    schema_version    SMALLINT      NOT NULL DEFAULT 1,
    CONSTRAINT ticks_pk PRIMARY KEY (instrument_id, provider_ts, provider_sequence)
);

SELECT create_hypertable(
    'ticks', 'provider_ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

SELECT add_retention_policy('ticks', INTERVAL '7 days', if_not_exists => TRUE);

COMMIT;

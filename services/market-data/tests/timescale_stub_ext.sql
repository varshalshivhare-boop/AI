-- Test-only additions to the TimescaleDB STUB used in the sandbox. Not the real extension.
CREATE FUNCTION add_compression_policy(rel text, compress_after interval,
    if_not_exists boolean DEFAULT false) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN RAISE NOTICE 'STUB add_compression_policy(%)', rel; RETURN 1; END $$;
CREATE FUNCTION add_retention_policy(rel text, drop_after interval,
    if_not_exists boolean DEFAULT false) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN RAISE NOTICE 'STUB add_retention_policy(%, %)', rel, drop_after; RETURN 1; END $$;

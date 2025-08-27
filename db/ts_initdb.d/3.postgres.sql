CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
SELECT version();
SELECT extname, extversion from pg_extension;

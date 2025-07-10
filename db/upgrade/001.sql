-- Idempotent upgrade script from unversioned to version 1.

ALTER TABLE physical_timeseries ADD COLUMN IF NOT EXISTS logical_uid INTEGER;
ALTER TABLE physical_timeseries ADD COLUMN IF NOT EXISTS received_at TIMESTAMPTZ;
ALTER TABLE physical_timeseries ADD COLUMN IF NOT EXISTS ts_delta INTERVAL;

ALTER TABLE physical_timeseries ALTER COLUMN received_at SET DEFAULT now();

UPDATE physical_timeseries SET received_at = ts WHERE received_at IS NULL;
UPDATE physical_timeseries SET ts_delta = received_at - ts WHERE ts_delta IS NULL;

CREATE OR REPLACE FUNCTION update_physical_timeseries_ts_delta()
RETURNS TRIGGER AS $$
BEGIN
  NEW.ts_delta = NEW.received_at - NEW.ts;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER update_physical_timeseries_ts_delta_trigger
BEFORE INSERT OR UPDATE ON physical_timeseries
FOR EACH ROW
EXECUTE FUNCTION update_physical_timeseries_ts_delta();

CREATE TABLE IF NOT EXISTS version (
    version INTEGER NOT NULL
);

ALTER TABLE version DROP CONSTRAINT IF EXISTS version_pkey;
ALTER TABLE version ADD CONSTRAINT version_pkey PRIMARY KEY (version);

ALTER TABLE physical_logical_map ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
INSERT INTO version (version) VALUES (1) ON CONFLICT (version) DO NOTHING;

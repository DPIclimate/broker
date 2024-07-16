CREATE TABLE timeseries (
                         broker_id TEXT NOT NULL,
                         l_uid INTEGER NOT NULL,
                         p_uid INTEGER NOT NULL,
                         timestamp TIMESTAMPTZ NOT NULL,
                         name TEXT,
                         value NUMERIC
                         );
                         
SELECT create_hypertable('timeseries', 'timestamp');

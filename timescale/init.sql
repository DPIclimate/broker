CREATE TABLE timeseries (
                         broker_id VARCHAR,
                         l_uid VARCHAR,
                         p_uid VARCHAR,
                         timestamp TIMESTAMPTZ NOT NULL,
                         name VARCHAR,
                         value NUMERIC
                         );

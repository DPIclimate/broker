CREATE TABLE timeseries (
                         broker_id VARCHAR,
                         l_uid VARCHAR,
                         p_uid VARCHAR,
                         timestamp TIMESTAMPTZ NOT NULL,
                         name VARCHAR,
                         value NUMERIC
                         );
                         
CREATE TABLE id_pairings (
                         pairing_id BIGSERIAL PRIMARY KEY,
                         l_uid VARCHAR,
                         p_uid VARCHAR
                         );

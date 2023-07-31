CREATE TABLE timeseries (
                         broker_id VARCHAR NOT NULL,
                         l_uid INTEGER NOT NULL,
                         p_uid INTEGER NOT NULL,
                         timestamp TIMESTAMPTZ NOT NULL,
                         name VARCHAR,
                         value NUMERIC
                         );
                         
CREATE TABLE id_pairings (
                         pairing_id BIGSERIAL PRIMARY KEY,
                         l_uid INTEGER NOT NULL,
                         p_uid INTEGER NOT NULL
                         );

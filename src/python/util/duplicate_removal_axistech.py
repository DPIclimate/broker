import dotenv
import psycopg2 as pg

dotenv.load_dotenv()

with pg.connect() as conn:
    conn.autocommit = True
    
    with conn.cursor() as curs:
        curs.execute("""
            WITH ranked_sensors AS (
                SELECT 
                    s1.row_id,
                    FIRST_VALUE(s1.row_id) OVER (
                        PARTITION BY s1.ts, s1.position, s1.variable, s1.location_id 
                        ORDER BY s1.row_id
                    ) AS duplicate_of
                FROM main.sensors s1
            )
            UPDATE main.sensors s
            SET dup_of_row = ranked_sensors.duplicate_of, err_data = true
            FROM ranked_sensors
            WHERE s.row_id = ranked_sensors.row_id
            AND ranked_sensors.row_id <> ranked_sensors.duplicate_of
            AND s.err_data = false
        """)

        print(f"Number of updated rows: {curs.rowcount}")
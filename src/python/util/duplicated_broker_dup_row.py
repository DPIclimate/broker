import dotenv
import psycopg as pg

dotenv.load_dotenv()

with pg.connect() as conn:
    conn.autocommit = True
    
    with conn.cursor() as curs:
        print("Duplicated records with the same correlation id")
        duplicated_broker_uuids = list(curs.execute(
            ''' 
            SELECT broker_correlation_id
            FROM main.sensors
            WHERE variable = 'battery_voltage' and position = 0
            GROUP BY broker_correlation_id
            HAVING COUNT(*) > 1
            '''
        ))

        for broker_uuid in duplicated_broker_uuids:
            curs.execute(
                """
                WITH FirstRows AS (
                    SELECT row_id, 
                        variable, 
                        position,
                        ROW_NUMBER() OVER (PARTITION BY variable, position ORDER BY row_id) AS row_num,
                        FIRST_VALUE(row_id) OVER (PARTITION BY variable, position ORDER BY row_id) AS first_row_id
                    FROM main.sensors
                    WHERE broker_correlation_id = %s
                )
                UPDATE main.sensors
                SET dup_of_row = fr.first_row_id, err_data = true
                FROM FirstRows fr
                WHERE main.sensors.row_id = fr.row_id
                AND fr.row_num > 1
                """, broker_uuid
            )
# Update the materialised views used to drive the Looker dashboards.
#
# Run this at 2:00am each day via cron with the line:
#
# 0 2 * * * /var/app/broker/db/refresh_ts_views.sh
#
docker exec -it prod-ts-1 psql -h localhost -U david -c 'refresh materialized view dt_sensors_soil_daily_mv' scmn_processed_data
docker exec -it prod-ts-1 psql -h localhost -U david -c 'refresh materialized view dt_sensors_soil_latest_mv' scmn_processed_data
docker exec -it prod-ts-1 psql -h localhost -U david -c 'refresh materialized view dt_temp_prec_monthly_agg_mv' scmn_processed_data

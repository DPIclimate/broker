# Update the materialised views used to drive the Looker dashboards.
#
# Run this at 2:00am each day via cron with the line:
#
# 0 2 * * * /path/to/repo/broker/db/refresh_ts_views.sh
#
echo ---------------------------------
export TZ=Australia/Sydney
date
psql -h localhost -c 'refresh materialized view dt_sensors_soil_daily_mv' scmn_processed_data
date
psql -h localhost -c 'refresh materialized view dt_sensors_soil_latest_mv' scmn_processed_data
date
psql -h localhost -c 'refresh materialized view dt_temp_prec_monthly_agg_mv' scmn_processed_data
date

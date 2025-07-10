create schema iota;
create table iota.measurement (
  ts                    timestamptz not null,
  broker_correlation_id uuid not null,
  puid                  integer not null,
  luid                  integer not null,
  location              geometry('POINT', 4283) null,
  name                  text not null,
  category              integer not null default 0,
  value double          precision not null
)
with (
  timescaledb.hypertable,
  timescaledb.partition_column='ts',
  timescaledb.chunk_interval = '1 month',
  timescaledb.orderby = 'ts desc'
);

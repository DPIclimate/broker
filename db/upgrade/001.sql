-- Upgrade from the last unversioned schema to version 1.

alter table physical_timeseries add column logical_uid integer;
alter table physical_timeseries add column received_at timestamptz;
alter table physical_timeseries add column ts_delta interval;

update physical_timeseries set received_at = ts where received_at is null;
update physical_timeseries set ts_delta = received_at - ts where ts_delta is null;

alter table physical_timeseries alter column received_at set default now();

create or replace function update_physical_timeseries_ts_delta()
returns trigger as $$
begin
  NEW.ts_delta = NEW.received_at - NEW.ts;
  return NEW;
end;
$$ language plpgsql;

create trigger update_physical_timeseries_ts_delta_trigger
before insert or update on physical_timeseries
for each row
execute function update_physical_timeseries_ts_delta();

create table if not exists version (
    version integer not null
);

alter table physical_logical_map add column is_active boolean not null default true;

insert into version values (1);

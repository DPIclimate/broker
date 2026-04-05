-- Add indexes for mapping and timeseries hot-path queries.

alter table physical_timeseries
    add column if not exists map_state smallint not null default 0;

-- Existing rows were already handled before this cutover.
update physical_timeseries
   set map_state = 2
 where map_state = 0;

alter table physical_timeseries
    drop constraint if exists pts_map_state_valid_ck;

alter table physical_timeseries
    add constraint pts_map_state_valid_ck
    check (map_state in (0, 1, 2, 3, 4));

create table if not exists logical_timeseries (
    uid integer generated always as identity primary key,
    physical_uid integer not null references physical_devices(uid),
    logical_uid integer not null references logical_devices(uid),
    received_at timestamptz,
    ts timestamptz not null,
    ts_delta interval,
    json_msg jsonb not null
);

create or replace function update_timeseries_ts_delta()
returns trigger as $$
begin
    NEW.ts_delta = NEW.received_at - NEW.ts;
    return NEW;
end;
$$ language plpgsql;

drop trigger if exists update_logical_timeseries_ts_delta_trigger on logical_timeseries;

create trigger update_logical_timeseries_ts_delta_trigger
before insert or update on logical_timeseries
for each row
execute function update_timeseries_ts_delta();

create index if not exists plm_current_physical_start_idx
    on physical_logical_map (physical_uid, start_time desc)
    where end_time is null;

create index if not exists plm_current_logical_start_idx
    on physical_logical_map (logical_uid, start_time desc)
    where end_time is null;

create index if not exists pts_physical_uid_ts_desc_idx
    on physical_timeseries (physical_uid, ts desc);

create index if not exists pts_logical_uid_ts_desc_idx
    on physical_timeseries (logical_uid, ts desc)
    where logical_uid is not null;

create index if not exists pts_pending_uid_idx
    on physical_timeseries (uid)
    where map_state = 0;

create index if not exists lts_physical_uid_ts_desc_idx
    on logical_timeseries (physical_uid, ts desc);

create index if not exists lts_logical_uid_ts_desc_idx
    on logical_timeseries (logical_uid, ts desc)
    where logical_uid is not null;

TRUNCATE version;
insert into version values (3);

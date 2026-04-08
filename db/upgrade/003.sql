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

alter table physical_logical_map
    add column if not exists uid integer generated always as identity;

alter table physical_logical_map
    add column if not exists active_range tstzrange;

do $$
begin
    if exists (
        select 1
        from pg_attribute
        where attrelid = 'physical_logical_map'::regclass
          and attname = 'start_time'
          and not attisdropped
    ) then
        execute '
            update physical_logical_map
               set active_range = tstzrange(start_time, end_time, ''[)'')
             where active_range is null
        ';
    end if;
end;
$$;

alter table physical_logical_map
    alter column active_range set default tstzrange(now(), null, '[)');

alter table physical_logical_map
    alter column active_range set not null;

alter table physical_logical_map
    drop constraint if exists end_gt_start;

alter table physical_logical_map
    drop constraint if exists physical_logical_map_logical_uid_start_time_key;

alter table physical_logical_map
    drop constraint if exists physical_logical_map_physical_uid_logical_uid_start_time_key;

alter table physical_logical_map
    drop constraint if exists plm_active_range_bounds_ck;

alter table physical_logical_map
    add constraint plm_active_range_bounds_ck check (
        lower_inc(active_range)
        and not upper_inc(active_range)
        and not isempty(active_range)
    );

alter table physical_logical_map
    drop column if exists start_time;

alter table physical_logical_map
    drop column if exists end_time;

alter table physical_logical_map
    drop constraint if exists physical_logical_map_pkey;

alter table physical_logical_map
    add constraint physical_logical_map_pkey primary key (uid);

drop index if exists plm_current_physical_start_idx;

drop index if exists plm_current_logical_start_idx;

drop index if exists plm_logical_lower_uidx;

drop index if exists plm_physical_logical_lower_uidx;

drop index if exists plm_current_physical_lower_idx;

drop index if exists plm_current_logical_lower_idx;

create unique index if not exists plm_logical_lower_uidx
    on physical_logical_map (logical_uid, lower(active_range));

create unique index if not exists plm_physical_logical_lower_uidx
    on physical_logical_map (physical_uid, logical_uid, lower(active_range));

create index if not exists plm_current_physical_lower_idx
    on physical_logical_map (physical_uid, lower(active_range) desc)
    where upper(active_range) is null;

create index if not exists plm_current_logical_lower_idx
    on physical_logical_map (logical_uid, lower(active_range) desc)
    where upper(active_range) is null;

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

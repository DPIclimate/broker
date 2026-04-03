-- Add indexes for mapping and timeseries hot-path queries.

alter table physical_timeseries
    add column if not exists map_state smallint not null default 0;

-- Existing rows were already handled before this cutover.
update physical_timeseries
   set map_state = 2
 where map_state = 0;

do $$
begin
    if not exists (
        select 1
          from pg_constraint
         where conname = 'pts_map_state_valid_ck'
    ) then
        alter table physical_timeseries
            add constraint pts_map_state_valid_ck
            check (map_state in (0, 1, 2, 3));
    end if;
end
$$;

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

TRUNCATE version;
insert into version values (3);

-- Add indexes for mapping and timeseries hot-path queries.

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

TRUNCATE version;
insert into version values (3);

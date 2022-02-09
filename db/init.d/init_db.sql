create table if not exists sources (
    source_name text primary key not null
);

create table if not exists physical_devices (
    uid integer generated always as identity primary key,
    source_name text not null references sources,
    name text not null,
    location point,
    last_seen timestamptz,
    properties jsonb not null default '{}'
);

create table if not exists ttn_messages (
    uid integer generated always as identity,
    correlation_id uuid unique not null,
    appid text not null,
    devid text not null,
    deveui text not null,
    ts timestamptz not null,
    msg jsonb not null,
    primary key (appid, devid, deveui, ts)
);

create table if not exists mace_messages (
    uid integer generated always as identity primary key,
    dev_serial text not null,
    ts timestamptz not null,
    msg text not null
);

create table if not exists logical_devices (
    uid integer generated always as identity primary key,
    name text not null,
    location point,
    last_seen timestamptz,
    properties jsonb not null default '{}'
);

create table if not exists physical_logical_map (
    uid integer generated always as identity primary key,
    physical_uid integer not null,
    logical_uid integer not null,
    start_time timestamptz not null default now()
);

insert into sources values ('ttn'), ('mace');

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
    uid integer generated always as identity primary key,
    appid text not null,
    devid text not null,
    deveui text not null,
    ts timestamptz not null,
    msg jsonb not null
);

create table if not exists mace_messages (
    uid integer generated always as identity primary key,
    dev_serial text not null,
    ts timestamptz not null,
    msg text not null
);

insert into sources values ('ttn'), ('mace');

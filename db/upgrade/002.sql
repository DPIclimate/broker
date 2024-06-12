CREATE EXTENSION postgis;
CREATE EXTENSION pgcrypto;

SELECT AddGeometryColumn('logical_devices','geom',4283,'POINT',2);
SELECT AddGeometryColumn('physical_devices','geom',4283,'POINT',2);

UPDATE logical_devices SET geom = ST_MakePoint(location[1], location[0]) WHERE location IS NOT NULL;
UPDATE physical_devices SET geom = ST_MakePoint(location[1], location[0]) WHERE location IS NOT NULL;

ALTER TABLE logical_devices DROP COLUMN location;
ALTER TABLE physical_devices DROP COLUMN location;

ALTER TABLE logical_devices RENAME COLUMN geom TO location;
ALTER TABLE physical_devices RENAME COLUMN geom TO location;

TRUNCATE version;
insert into version values (2);

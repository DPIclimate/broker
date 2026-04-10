# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.contrib.gis.db import models
from django.contrib.postgres.fields import DateTimeRangeField


class DeviceBlob(models.Model):
    uid = models.AutoField(primary_key=True)
    physical_uid = models.ForeignKey('PhysicalDevice', models.DO_NOTHING, db_column='physical_uid', blank=True, null=True)
    ts = models.DateTimeField()
    data = models.BinaryField()

    class Meta:
        managed = False
        db_table = 'device_blobs'


class DeviceNote(models.Model):
    uid = models.AutoField(primary_key=True)
    physical_uid = models.ForeignKey('PhysicalDevice', models.DO_NOTHING, db_column='physical_uid', blank=True, null=True)
    ts = models.DateTimeField()
    note = models.TextField()

    class Meta:
        managed = False
        db_table = 'device_notes'


class LogicalDevice(models.Model):
    uid = models.AutoField(primary_key=True)
    name = models.TextField()
    location = models.PointField(blank=True, null=True, srid=4283)
    last_seen = models.DateTimeField(blank=True, null=True)
    properties = models.JSONField()

    class Meta:
        managed = False
        db_table = 'logical_devices'


class PhysicalDevice(models.Model):
    uid = models.AutoField(primary_key=True)
    source_name = models.ForeignKey('Source', models.DO_NOTHING, db_column='source_name')
    name = models.TextField()
    location = models.PointField(blank=True, null=True, srid=4283)
    last_seen = models.DateTimeField(blank=True, null=True)
    source_ids = models.JSONField(blank=True, null=True)
    properties = models.JSONField()

    class Meta:
        managed = False
        db_table = 'physical_devices'


class PhysicalLogicalMap(models.Model):
    uid = models.AutoField(primary_key=True)
    physical_uid = models.ForeignKey(PhysicalDevice, models.DO_NOTHING, db_column='physical_uid')
    logical_uid = models.ForeignKey(LogicalDevice, models.DO_NOTHING, db_column='logical_uid')
    active_range = DateTimeRangeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'physical_logical_map'


class PhysicalTimeseries(models.Model):
    uid = models.AutoField(primary_key=True)
    physical_uid = models.ForeignKey(PhysicalDevice, models.DO_NOTHING, db_column='physical_uid')
    logical_uid = models.IntegerField(blank=True, null=True)
    map_state = models.SmallIntegerField(default=0)
    received_at = models.DateTimeField()
    ts = models.DateTimeField()
    ts_delta = models.DurationField(blank=True, null=True)
    json_msg = models.JSONField()

    class Meta:
        managed = False
        db_table = 'physical_timeseries'


class LogicalTimeseries(models.Model):
    uid = models.AutoField(primary_key=True)
    physical_uid = models.ForeignKey(PhysicalDevice, models.DO_NOTHING, db_column='physical_uid')
    logical_uid = models.IntegerField(blank=True, null=True)
    received_at = models.DateTimeField()
    ts = models.DateTimeField()
    ts_delta = models.DurationField(blank=True, null=True)
    json_msg = models.JSONField()

    class Meta:
        managed = False
        db_table = 'logical_timeseries'


class RawMessage(models.Model):
    uid = models.AutoField(primary_key=True)
    source_name = models.ForeignKey('Source', models.DO_NOTHING, db_column='source_name')
    physical_uid = models.IntegerField(blank=True, null=True)
    correlation_id = models.UUIDField(unique=True)
    ts = models.DateTimeField()
    json_msg = models.JSONField(blank=True, null=True)
    text_msg = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'raw_messages'


class Source(models.Model):
    source_name = models.TextField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'sources'


class User(models.Model):
    uid = models.AutoField(primary_key=True)
    username = models.TextField(unique=True)
    salt = models.TextField()
    password = models.TextField()
    auth_token = models.TextField()
    valid = models.BooleanField()
    read_only = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'users'

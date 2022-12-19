class PhysicalDevice:
    def __init__(self, uid, name, source_name, last_seen):
        self.uid = uid
        self.name = name
        self.source_name = source_name
        self.last_seen = last_seen

class LogicalDevice:
    def __init__(self, uid, name, location, last_seen):
        self.uid = uid
        self.name = name
        self.location = location
        self.last_seen = last_seen

class DeviceMapping:
    def __init__(self, ld_uid, ld_name, pd_uid, pd_name, start_time, end_time):
        self.ld_uid = ld_uid
        self.ld_name = ld_name
        self.pd_uid = pd_uid
        self.pd_name = pd_name
        self.start_time = start_time
        self.end_time = end_time

class DeviceNote:
    def __init__(self, note, ts, uid):
        self.note = note
        self.uid = uid
        self.ts = ts
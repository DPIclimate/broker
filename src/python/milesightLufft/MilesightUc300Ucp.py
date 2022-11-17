# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 9):
    raise Exception("Incompatible Kaitai Struct Python API: 0.9 or later is required, but you have %s" % (kaitaistruct.__version__))

class MilesightUc300Ucp(KaitaiStruct):
    def __init__(self, _io, _parent=None, _root=None):
        self._io = _io
        self._parent = _parent
        self._root = _root if _root else self
        self._read()

    def _read(self):
        self.reports = []
        i = 0
        while not self._io.is_eof():
            self.reports.append(MilesightUc300Ucp.ReportEntry(self._io, self, self._root))
            i += 1


    class MbEntry(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.channel = self._io.read_bits_int_be(4)
            self.data_type = self._io.read_bits_int_be(4)
            self._io.align_to_byte()
            self.toggles = MilesightUc300Ucp.MbToggles(self._io, self, self._root)
            if self.toggles.collected:
                self.values = []
                for i in range(self.toggles.quantity):
                    _on = self.toggles.signed
                    if _on == False:
                        self.values.append(self._io.read_u2le())
                    elif _on == True:
                        self.values.append(self._io.read_s2le())


            if self.toggles.collected == False:
                self._unnamed4 = self._io.read_s1()



    class AiValues(KaitaiStruct):
        """For each analog input, if data has been successfully collected..."""
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            if self._parent.toggles.ai_010v_2 == 1:
                self.ai_010v_2 = self._io.read_f4le()

            if self._parent.toggles.ai_010v_1 == 1:
                self.ai_010v_1 = self._io.read_f4le()

            if self._parent.toggles.ai_420ma_2 == 1:
                self.ai_420ma_2 = self._io.read_f4le()

            if self._parent.toggles.ai_420ma_1 == 1:
                self.ai_420ma_1 = self._io.read_f4le()

            if self._parent.toggles.ai_pt100_2 == 1:
                self.ai_pt100_2 = self._io.read_f4le()

            if self._parent.toggles.ai_pt100_1 == 1:
                self.ai_pt100_1 = self._io.read_f4le()



    class ReportEntry(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.start = self._io.read_bytes(1)
            if not self.start == b"\x7E":
                raise kaitaistruct.ValidationNotEqualError(b"\x7E", self.start, self._io, u"/types/report_entry/seq/0")
            self.data_type = self._io.read_u1()
            self.packet_length = self._io.read_u2le()
            _on = self.data_type
            if _on == 243:
                self._raw_data = self._io.read_bytes((self.packet_length - 5))
                _io__raw_data = KaitaiStream(BytesIO(self._raw_data))
                self.data = MilesightUc300Ucp.AttributeReport(_io__raw_data, self, self._root)
            elif _on == 244:
                self._raw_data = self._io.read_bytes((self.packet_length - 5))
                _io__raw_data = KaitaiStream(BytesIO(self._raw_data))
                self.data = MilesightUc300Ucp.RegularReport(_io__raw_data, self, self._root)
            else:
                self._raw_data = self._io.read_bytes((self.packet_length - 5))
                _io__raw_data = KaitaiStream(BytesIO(self._raw_data))
                self.data = MilesightUc300Ucp.UnsupportedReport(_io__raw_data, self, self._root)
            self.end = self._io.read_bytes(1)
            if not self.end == b"\x7E":
                raise kaitaistruct.ValidationNotEqualError(b"\x7E", self.end, self._io, u"/types/report_entry/seq/4")


    class DiStatus(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self._unnamed0 = self._io.read_bits_int_be(4)
            self.di_4 = self._io.read_bits_int_be(1) != 0
            self.di_3 = self._io.read_bits_int_be(1) != 0
            self.di_2 = self._io.read_bits_int_be(1) != 0
            self.di_1 = self._io.read_bits_int_be(1) != 0


    class RegularReport(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.packet_version = self._io.read_u1()
            self.timestamp = self._io.read_u4le()
            self.signal_strength = self._io.read_u1()
            self.digital_outputs = MilesightUc300Ucp.Do(self._io, self, self._root)
            self.digital_inputs = MilesightUc300Ucp.Di(self._io, self, self._root)
            self.analog_inputs = MilesightUc300Ucp.Ai(self._io, self, self._root)
            self.modbus_inputs = []
            i = 0
            while not self._io.is_eof():
                self.modbus_inputs.append(MilesightUc300Ucp.MbEntry(self._io, self, self._root))
                i += 1



    class Do(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.toggles = MilesightUc300Ucp.DoToggles(self._io, self, self._root)
            if  ((self.toggles.do_2) or (self.toggles.do_1)) :
                self.status = MilesightUc300Ucp.DoStatus(self._io, self, self._root)



    class Di(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.toggles = MilesightUc300Ucp.DiToggles(self._io, self, self._root)
            if  ((self.toggles.di_1 == 1) or (self.toggles.di_2 == 1) or (self.toggles.di_3 == 1) or (self.toggles.di_4 == 1)) :
                self.status = MilesightUc300Ucp.DiStatus(self._io, self, self._root)

            if  ((self.toggles.di_1 == 2) or (self.toggles.di_1 == 3) or (self.toggles.di_2 == 2) or (self.toggles.di_2 == 3) or (self.toggles.di_3 == 2) or (self.toggles.di_3 == 3) or (self.toggles.di_4 == 2) or (self.toggles.di_4 == 3)) :
                self.counters = MilesightUc300Ucp.DiCounters(self._io, self, self._root)



    class MbToggles(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.signed = self._io.read_bits_int_be(1) != 0
            self.decimal_place = self._io.read_bits_int_be(3)
            self.collected = self._io.read_bits_int_be(1) != 0
            self.quantity = self._io.read_bits_int_be(3)


    class DiToggles(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.di_4 = self._io.read_bits_int_be(2)
            self.di_3 = self._io.read_bits_int_be(2)
            self.di_2 = self._io.read_bits_int_be(2)
            self.di_1 = self._io.read_bits_int_be(2)


    class UnsupportedReport(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.data = (self._io.read_bytes(self._parent.packet_length)).decode(u"UTF-8")


    class DoStatus(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self._unnamed0 = self._io.read_bits_int_be(6)
            self.do_1 = self._io.read_bits_int_be(1) != 0
            self.do_2 = self._io.read_bits_int_be(1) != 0


    class Ai(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.toggles = MilesightUc300Ucp.AiToggles(self._io, self, self._root)
            if  ((self.toggles.ai_010v_2 == 1) or (self.toggles.ai_010v_1 == 1) or (self.toggles.ai_420ma_2 == 1) or (self.toggles.ai_420ma_1 == 1) or (self.toggles.ai_pt100_2 == 1) or (self.toggles.ai_pt100_1 == 1)) :
                self.values = MilesightUc300Ucp.AiValues(self._io, self, self._root)



    class AiToggles(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.ai_010v_2 = self._io.read_bits_int_be(2)
            self.ai_010v_1 = self._io.read_bits_int_be(2)
            self.ai_420ma_2 = self._io.read_bits_int_be(2)
            self.ai_420ma_1 = self._io.read_bits_int_be(2)
            self._unnamed4 = self._io.read_bits_int_be(4)
            self.ai_pt100_2 = self._io.read_bits_int_be(2)
            self.ai_pt100_1 = self._io.read_bits_int_be(2)


    class AttributeReport(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.packet_version = self._io.read_u1()
            self.ucp_version = self._io.read_u1()
            self.serial_number = (self._io.read_bytes(16)).decode(u"UTF-8")
            self.hardware_version = (self._io.read_bytes(4)).decode(u"UTF-8")
            self.software_version = (self._io.read_bytes(4)).decode(u"UTF-8")
            self.imei = (self._io.read_bytes(15)).decode(u"UTF-8")
            self.imsi = (self._io.read_bytes(15)).decode(u"UTF-8")
            self.iccid = (self._io.read_bytes(20)).decode(u"UTF-8")


    class DiCounters(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            if  ((self._parent.toggles.di_1 == 2) or (self._parent.toggles.di_1 == 3)) :
                self.di_1 = self._io.read_u4le()

            if  ((self._parent.toggles.di_2 == 2) or (self._parent.toggles.di_2 == 3)) :
                self.di_2 = self._io.read_u4le()

            if  ((self._parent.toggles.di_3 == 2) or (self._parent.toggles.di_3 == 3)) :
                self.di_3 = self._io.read_u4le()

            if  ((self._parent.toggles.di_4 == 2) or (self._parent.toggles.di_4 == 3)) :
                self.di_4 = self._io.read_u4le()



    class DoToggles(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self._unnamed0 = self._io.read_bits_int_be(6)
            self.do_2 = self._io.read_bits_int_be(1) != 0
            self.do_1 = self._io.read_bits_int_be(1) != 0





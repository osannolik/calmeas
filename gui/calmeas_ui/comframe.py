import ctypes
import time
from array import array

import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')


FRAME_START = ord('s')
FRAME_HEADER_SIZE = 3
FRAME_DATA_SIZE_MAX = 512
FRAME_SIZE_RAW_MAX = FRAME_DATA_SIZE_MAX+FRAME_HEADER_SIZE


class Frame_Data(ctypes.Structure):
    _pack_ = 1
    _fields_ = [ ('raw',        ctypes.c_uint8 * FRAME_DATA_SIZE_MAX) ]

class Frame_Data_Fields(ctypes.Union):
    _pack_ = 1
    _fields_ =  [ ('b',          Frame_Data),
                  ('var_uint8',  ctypes.c_uint8 * FRAME_DATA_SIZE_MAX),
                  ('var_uint16', ctypes.c_uint16 * (FRAME_DATA_SIZE_MAX / 2)),
                  ('var_uint32', ctypes.c_uint32 * (FRAME_DATA_SIZE_MAX / 4)),
                  ('var_int8',   ctypes.c_int8 * FRAME_DATA_SIZE_MAX),
                  ('var_int16',  ctypes.c_int16 * (FRAME_DATA_SIZE_MAX / 2)),
                  ('var_int32',  ctypes.c_int32 * (FRAME_DATA_SIZE_MAX / 4)),
                  ('var_float',  ctypes.c_float * (FRAME_DATA_SIZE_MAX / 4)), ]
    _anonymous_ = ('b')

class Frame_Status_Bits(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('interface', ctypes.c_uint8,  4),
                ('mid',       ctypes.c_uint8,  4)]

class Frame_Status(ctypes.Union):
    _pack_ = 1
    _fields_ =  [ ('b',    Frame_Status_Bits),
                  ('full', ctypes.c_uint8)]
    _anonymous_ = ('b')

class Frame_Bits(ctypes.Structure):
    _pack_ = 1
    _fields_ = [ ('data_size', ctypes.c_uint16),
                 ('_status',   Frame_Status), 
                 ('data',      Frame_Data_Fields) ]

class Frame_raw(ctypes.Union):
    _pack_ = 1
    _fields_ =  [ ('b',   Frame_Bits),
                  ('raw', ctypes.c_uint8 * FRAME_SIZE_RAW_MAX) ]
    _anonymous_ = ('b')


def _ByteSwap32(data):
    return ( (data&0x000000FF)<<24 | (data&0x0000FF00)<<8 | (data&0x00FF0000)>>8 | (data&0xFF000000)>>24 )

def _ByteSwap16(data):
    return ( (data&0x00FF)<<8 | (data&0xFF00)>>8 )

def _ByteSwapFloat(x):
    f = array('f',[x])
    f.byteswap()
    return f[0]

CRC8_INIT  = 0x00
CRC8_TABLE = [
    0x00, 0x5e, 0xbc, 0xe2, 0x61, 0x3f, 0xdd, 0x83, 0xc2, 0x9c, 0x7e, 0x20, 0xa3,
    0xfd, 0x1f, 0x41, 0x9d, 0xc3, 0x21, 0x7f, 0xfc, 0xa2, 0x40, 0x1e, 0x5f, 0x01,
    0xe3, 0xbd, 0x3e, 0x60, 0x82, 0xdc, 0x23, 0x7d, 0x9f, 0xc1, 0x42, 0x1c, 0xfe,
    0xa0, 0xe1, 0xbf, 0x5d, 0x03, 0x80, 0xde, 0x3c, 0x62, 0xbe, 0xe0, 0x02, 0x5c,
    0xdf, 0x81, 0x63, 0x3d, 0x7c, 0x22, 0xc0, 0x9e, 0x1d, 0x43, 0xa1, 0xff, 0x46,
    0x18, 0xfa, 0xa4, 0x27, 0x79, 0x9b, 0xc5, 0x84, 0xda, 0x38, 0x66, 0xe5, 0xbb,
    0x59, 0x07, 0xdb, 0x85, 0x67, 0x39, 0xba, 0xe4, 0x06, 0x58, 0x19, 0x47, 0xa5,
    0xfb, 0x78, 0x26, 0xc4, 0x9a, 0x65, 0x3b, 0xd9, 0x87, 0x04, 0x5a, 0xb8, 0xe6,
    0xa7, 0xf9, 0x1b, 0x45, 0xc6, 0x98, 0x7a, 0x24, 0xf8, 0xa6, 0x44, 0x1a, 0x99,
    0xc7, 0x25, 0x7b, 0x3a, 0x64, 0x86, 0xd8, 0x5b, 0x05, 0xe7, 0xb9, 0x8c, 0xd2,
    0x30, 0x6e, 0xed, 0xb3, 0x51, 0x0f, 0x4e, 0x10, 0xf2, 0xac, 0x2f, 0x71, 0x93,
    0xcd, 0x11, 0x4f, 0xad, 0xf3, 0x70, 0x2e, 0xcc, 0x92, 0xd3, 0x8d, 0x6f, 0x31,
    0xb2, 0xec, 0x0e, 0x50, 0xaf, 0xf1, 0x13, 0x4d, 0xce, 0x90, 0x72, 0x2c, 0x6d,
    0x33, 0xd1, 0x8f, 0x0c, 0x52, 0xb0, 0xee, 0x32, 0x6c, 0x8e, 0xd0, 0x53, 0x0d,
    0xef, 0xb1, 0xf0, 0xae, 0x4c, 0x12, 0x91, 0xcf, 0x2d, 0x73, 0xca, 0x94, 0x76,
    0x28, 0xab, 0xf5, 0x17, 0x49, 0x08, 0x56, 0xb4, 0xea, 0x69, 0x37, 0xd5, 0x8b,
    0x57, 0x09, 0xeb, 0xb5, 0x36, 0x68, 0x8a, 0xd4, 0x95, 0xcb, 0x29, 0x77, 0xf4,
    0xaa, 0x48, 0x16, 0xe9, 0xb7, 0x55, 0x0b, 0x88, 0xd6, 0x34, 0x6a, 0x2b, 0x75,
    0x97, 0xc9, 0x4a, 0x14, 0xf6, 0xa8, 0x74, 0x2a, 0xc8, 0x96, 0x15, 0x4b, 0xa9,
    0xf7, 0xb6, 0xe8, 0x0a, 0x54, 0xd7, 0x89, 0x6b, 0x35]

CRC_LEN_TX = 1
CRC_LEN_RX = 0

def crc8_block(data, crc_init = CRC8_INIT):
    crc = crc_init
    for d in data:
        crc = CRC8_TABLE[crc ^ (d&0xFF)]

    return crc

class ComFrame(Frame_raw):
    
    def __init__(self, frameBytes=None):
        self.timestamp = time.time()
        self.frame_size_raw = 0
        self.data_size = 0
        self._isValid = False
        self._fieldDef = Frame_Bits()

        if frameBytes is not None:
            self.AddFrameBytes(frameBytes)

    def interface():
        doc = "The interface property."
        def fget(self):
            return self._status.interface
        def fset(self, value):
            self._status.interface = value
        def fdel(self):
            del self._status.interface
        return locals()
    interface = property(**interface())

    def mid():
        doc = "The mid property."
        def fget(self):
            return self._status.mid
        def fset(self, value):
            self._status.mid = value
        def fdel(self):
            del self._status.mid
        return locals()
    mid = property(**mid())

    def status():
        doc = "The status property."
        def fget(self):
            return self._status.full
        def fset(self, value):
            self._status.full = value
        def fdel(self):
            del self._status.full
        return locals()
    status = property(**status())

    def Fields(self):
        return [x[0] for x in self._fieldDef._fields_]

    def AddFrameBytes(self, frameBytes, has_start_byte = True, do_assert = True, crc_len = CRC_LEN_RX):
        if frameBytes:
            if has_start_byte:
                startByte = frameBytes[0]
                del frameBytes[0]
            else:
                startByte=FRAME_START

        self.frame_size_raw = len(frameBytes)

        if do_assert:
            self._isValid = (FRAME_HEADER_SIZE <= self.frame_size_raw <= FRAME_SIZE_RAW_MAX) and (startByte==FRAME_START)

        if (do_assert and self._isValid) or not do_assert:
            for i,b in enumerate(frameBytes):
                self.raw[i] = ctypes.c_uint8(b)

        if do_assert:
            self._isValid = (int(self.data_size) == self.frame_size_raw-FRAME_HEADER_SIZE)

    def setData(self, data, calculate_length=True, endian='big', crc_len = CRC_LEN_TX):
        data.reverse()

        if endian=='big':
            swap16 = lambda x: x
            swap32 = lambda x: x
            swapFloat = lambda x: x
        else:
            swap16 = _ByteSwap16
            swap32 = _ByteSwap32
            swapFloat = _ByteSwapFloat

        fd = Frame_Data_Fields()

        for i,d in enumerate(data):
            if type(d)==int:
                data[i] = ctypes.c_uint32(d)
            elif type(d)==float:
                data[i] = ctypes.c_float(d)

        totaldatabytelength = 0

        for b in data:

            entrysize = ctypes.sizeof(type(b))

            fd.raw[entrysize:] = fd.raw[:-entrysize]

            totaldatabytelength += entrysize

            if type(b)==ctypes.c_uint8:
                fd.var_uint8[0] = b
            elif type(b)==ctypes.c_int8:
                fd.var_int8[0] = b
            elif type(b)==ctypes.c_uint16:
                fd.var_uint16[0] = ctypes.c_uint16(swap16(b.value))
            elif type(b)==ctypes.c_int16:
                fd.var_int16[0] = ctypes.c_int16(swap16(b.value))
            elif type(b)==ctypes.c_uint32:
                fd.var_uint32[0] = ctypes.c_uint32(swap32(b.value))
            elif type(b)==ctypes.c_int32:
                fd.var_int32[0] = ctypes.c_int32(swap32(b.value))
            elif type(b)==ctypes.c_float:
                fd.var_float[0] = ctypes.c_float(swapFloat(b.value))

        if calculate_length:
            self.data_size = ctypes.c_uint16(swap16(totaldatabytelength))
            self.frame_size_raw = FRAME_HEADER_SIZE + totaldatabytelength + crc_len

        if crc_len == 1:
            crc = crc8_block([self.status])
            fd.raw[totaldatabytelength] = ctypes.c_uint8(crc8_block(fd.raw[:totaldatabytelength], crc))

        self.data = fd

    def getData(self, dataTypeStructure, endian='big'):
        data = list()

        if endian=='big':
            swap16 = lambda x: x
            swap32 = lambda x: x
            swapFloat = lambda x: x
        else:
            swap16 = _ByteSwap16
            swap32 = _ByteSwap32
            swapFloat = _ByteSwapFloat

        for i,t in enumerate(dataTypeStructure):
            if t==int:
                dataTypeStructure[i] = ctypes.c_uint32
            elif t==float:
                dataTypeStructure[i] = ctypes.c_float

        for t in dataTypeStructure:

            entrysize = ctypes.sizeof(t)

            if t==ctypes.c_uint8:
                data.append( t(self.data.var_uint8[0]) )
            elif t==ctypes.c_float:
                data.append( t(self.data.var_float[0]) )
            elif t==ctypes.c_uint32:
                data.append( t(self.data.var_uint32[0]) )
            elif t==ctypes.c_int32:
                data.append( t(self.data.var_int32[0]) )
            elif t==ctypes.c_int8:
                data.append( t(self.data.var_int8[0]) )
            elif t==ctypes.c_uint16:
                data.append( t(self.data.var_uint16[0]) )
            elif t==ctypes.c_int16:
                data.append( t(self.data.var_int16[0]) )

            self.data.raw[:-entrysize] = self.data.raw[entrysize:]

        return data

    def GetFrameBytesRaw(self, with_start=False):
        bytes = bytearray()

        if with_start:
            bytes.append(FRAME_START)

        for i in range(self.frame_size_raw):
            bytes.append(self.raw[i])

        return bytes

    def FrameBytesFormatted(self, formatting='x', spacing=' '):
        frame_str = ['{:#'+formatting+'}'] * self.frame_size_raw

        return spacing.join(frame_str).format(*self.GetFrameBytesRaw())

    def Validity(self):
        return self._isValid

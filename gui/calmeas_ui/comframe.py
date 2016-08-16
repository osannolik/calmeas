import ctypes
import time
from array import array

import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')


FRAME_START = ord('s')
FRAME_HEADER_SIZE = 2
FRAME_DATA_SIZE_MAX = 256
FRAME_SIZE_RAW_MAX = FRAME_DATA_SIZE_MAX+FRAME_HEADER_SIZE


class Frame_Data(ctypes.Structure):
    _pack_ = 1
    _fields_ = [ ('raw',        ctypes.c_uint8 * FRAME_DATA_SIZE_MAX) ]

class Frame_Data_Fields(ctypes.Union):
    _pack_ = 1
    _fields_ =  [ ('b',         Frame_Data),
                  ('var_uint8', ctypes.c_uint8 * FRAME_DATA_SIZE_MAX),
                  ('var_uint16', ctypes.c_uint16 * (FRAME_DATA_SIZE_MAX / 2)),
                  ('var_uint32', ctypes.c_uint32 * (FRAME_DATA_SIZE_MAX / 4)),
                  ('var_int8',  ctypes.c_int8 * FRAME_DATA_SIZE_MAX),
                  ('var_int16', ctypes.c_int16 * (FRAME_DATA_SIZE_MAX / 2)),
                  ('var_int32', ctypes.c_int32 * (FRAME_DATA_SIZE_MAX / 4)),
                  ('var_float', ctypes.c_float * (FRAME_DATA_SIZE_MAX / 4)), ]
    _anonymous_ = ('b')

class Frame_Bits(ctypes.Structure):
    _pack_ = 1
    _fields_ = [ ('interface',  ctypes.c_uint8, 4),
                 ('mid',        ctypes.c_uint8, 4),
                 ('data_size',  ctypes.c_uint8, 8),
                 ('data',       Frame_Data_Fields) ]

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

class ComFrame(Frame_raw):
    
    def __init__(self, frameBytes=None):
        self.timestamp = time.time()
        self.frame_size_raw = 0
        self.data_size = 0
        self._isValid = False
        self._fieldDef = Frame_Bits()

        if frameBytes is not None:
            self.AddFrameBytes(frameBytes)

    def Fields(self):
        return [x[0] for x in self._fieldDef._fields_]

    def AddFrameBytes(self, frameBytes, has_start_byte = True, do_assert = True):
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

    def setData(self, data, calculate_length=True, endian='big'):
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

        totalbytelength = 0

        for b in data:

            entrysize = ctypes.sizeof(type(b))

            fd.raw[entrysize:] = fd.raw[:-entrysize]

            totalbytelength += entrysize

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

        self.data = fd

        if calculate_length:
            self.data_size = totalbytelength
            self.frame_size_raw = FRAME_HEADER_SIZE + totalbytelength

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

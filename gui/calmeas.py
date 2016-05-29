from comcommands import putResponseData, getResponseData
from comcommands import ComCommands
from comframe import ComFrame

import numpy as np
import ctypes
import Queue
import copy

import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

CALMEAS_INTERFACE = 3

CALMEAS_ID_META = 0
CALMEAS_ID_ALL = 1
CALMEAS_ID_STREAM_ALL = 2
CALMEAS_ID_RASTER = 3
CALMEAS_ID_RASTER_SET = 4
CALMEAS_ID_SYMBOL_NAME = 5
CALMEAS_ID_SYMBOL_DESC = 6
CALMEAS_ID_RASTER_PERIODS = 7

SET_COPIED_KEY = 'copy from'
SET_DATA_KEY = 'data'

class SymbolDataType():
    def __init__(self, basetype=np.uint8):
        self.enumerations = dict()

        # If enum get enum items.
        # From datatype configuration file?

        self.np_basetype = basetype
        self.text = basetype.__name__

    def size(self):
        return np.dtype(self.np_basetype).itemsize

    def isEnum(self):
        return len(self.enumerations)!=0

    def isInteger(self):
        return (self.np_basetype in [np.uint8, np.int8, np.uint16, np.int16, np.uint32, np.int32])

    def isFloating(self):
        return (self.np_basetype in [np.float, np.double])

    def isSigned(self):
        return self.isFloating() or np.iinfo(self.np_basetype).min<0

    def basetypeToStr(self, value):
        if value is None:
            return ''

        if self.isEnum():
            if value in self.enumerations.keys():
                return self.enumerations[value]
            else:
                return ''
        else:
            if self.isFloating():
                return '{:.6f}'.format(value)
            else:
                try:
                    return str(value[0])
                except:
                    return str(value)

class Symbol():
    def __init__(self, name=""):
        self._datatype = None
        self.name = name

        self.index = -1
        self.address = 0
        self.nameAddress = 0
        self.descAddress = 0

        self.desc = ""

        self.setDatatype(SymbolDataType())
        self.setPeriod(0.0)

    def __str__(self):
        return self.info()

    def info(self, short=False):
        if short:
            return '{} {}'.format(s.name, s.datatype.text)
        else:
            return '{} {} {} {} {} 0x{:x}'.format(s.name, s.datatype.text, s.period_s, s.desc, s.index, s.address)

    @property
    def datatype(self):
        return self._datatype

    def setDatatype(self, datatype):
        self._datatype = datatype

        if self._datatype.isEnum():
            self.getValue = self.getValueStr
        else:
            self.getValue = self.getValueRaw

        self.initDataBuffer()

    def getValueStr(self, raw=None):
        if raw is None:
            return self._datatype.basetypeToStr(self.getValueRaw())
        else:
            return self._datatype.basetypeToStr(raw)

    def getValueRaw(self):
        if len(self.data)>0:
            return self.data[-1]
        else:
            return None

    def setValue(self, val):

        self.data[:-1] = self.data[1:]
        self.data[-1] = val

        self.time[:-1] = self.time[1:]
        self.time[-1] = self.time[-2] + self.period_s

    def initDataBuffer(self, size=10000):
        self.data = np.zeros(size, dtype=self._datatype.np_basetype)
        self.time = np.zeros(size)

    def setPeriod(self, p):
        self.period_s = p

    def initForSampling(self, timeRange):
        self.initDataBuffer(size=int(timeRange/self.period_s))

class CalMeas():
    def __init__(self, comhandler):
        self._comhandler = comhandler

        self._comhandler.enableInterface(CALMEAS_INTERFACE, self.interfaceCallback)

        self.comcmds = ComCommands(self._comhandler)

        self._ID_CallBacks = {CALMEAS_ID_META:           self.ID_Meta_Callback,
                              CALMEAS_ID_ALL:            self.ID_All_Callback,
                              CALMEAS_ID_STREAM_ALL:     self.ID_StreamAll_Callback,
                              CALMEAS_ID_RASTER:         self.ID_Raster_Callback,
                              CALMEAS_ID_RASTER_SET:     self.ID_RasterSet_Callback,
                              CALMEAS_ID_SYMBOL_NAME:    self.ID_SymbolName_Callback,
                              CALMEAS_ID_SYMBOL_DESC:    self.ID_SymbolDesc_Callback,
                              CALMEAS_ID_RASTER_PERIODS: self.ID_RasterPeriods_Callback}

        self._TypeCodeTable = {0x01: (ctypes.c_uint8,  np.uint8),
                               0x81: (ctypes.c_int8,   np.int8),
                               0x02: (ctypes.c_uint16, np.uint16),
                               0x82: (ctypes.c_int16,  np.int16),
                               0x04: (ctypes.c_uint32, np.uint32),
                               0x84: (ctypes.c_int32,  np.int32),
                               0x94: (ctypes.c_float,  np.float)}


        self._ResponseFifo = Queue.Queue()

        self.isStarted = False
        self.targetSymbols = dict()
        self.workingSymbols = dict()

        
        self.paramSet = dict()
        self.workingParamSet = ''

        self._nbrOfRasters = 3

        self._streamDataStructure = list()
        self.rasterPeriods = list()
        self.raster = list()
        self.rasterDataStructures = list()

        for r in range(self._nbrOfRasters):
            self.raster.append(list())
            self.rasterDataStructures.append(list())



    def importParamSet(self, name, setData):
        # Todo: Check that all symbols exist etc...
        self.paramSet[name] = copy.deepcopy(setData)

    def newParamSet(self, name, fromSet=''):
        fromSet = str(fromSet)
        if self.paramSet:
            # Make a copy
            if fromSet in self.paramSet.keys():
                pset = copy.deepcopy(self.paramSet[fromSet])
            else:
                raise Exception('Not an existing data set "{}"'.format(fromSet))
        else:
            pset = dict()
            pset[SET_DATA_KEY] = dict()

        pset[SET_COPIED_KEY] = fromSet
        self.paramSet[str(name)] = pset

    def deleteParamSet(self, name):
        if name!=self.workingParamSet and name in self.paramSet.keys():
            del self.paramSet[name]
        else:
            raise Exception('Cannot remove data set "{}"'.format(name))

    def getParamSet(self, name):
        return dict(self.paramSet[str(name)][SET_DATA_KEY])

    def useParamSet(self, useSet):
        useSet = str(useSet)
        if useSet in self.paramSet.keys():
            self.workingParamSet = str(useSet)

            for symbolName, data in self.paramSet[useSet][SET_DATA_KEY].iteritems():
                self.tuneTargetParameter(symbolName, data)

        else:
            raise Exception('Not an existing data set "{}"'.format(useSet))

    def addParam(self, symbolName, toSet=''):
        toSet = str(toSet)
        if toSet=='': 
            toSet = self.workingParamSet

        if toSet in self.paramSet.keys():
            val = self.getSymbolTargetValue(symbolName)
            self.paramSet[toSet][SET_DATA_KEY][symbolName] = val[0]
        else:
            raise Exception('Not an existing data set "{}"'.format(toSet))

    def getSymbolTargetValue(self, symbolName):
        if symbolName in self.workingSymbols.keys():
            symbolAddress = self.workingSymbols[symbolName].address
            symbolType = self.workingSymbols[symbolName].datatype
            tc = self.getTypeCode( symbolType.np_basetype )
            c_type = self.getBaseType(tc)[0]

            self.comcmds.requestRead(symbolAddress, [c_type])
            (addr, data) = self.comcmds.pollReadData(timeout=1)

            return data

        else:
            return None

    def tuneTargetParameter(self, symbolName, value):
        if symbolName in self.workingSymbols.keys():
            symbolAddress = self.workingSymbols[symbolName].address
            symbolType = self.workingSymbols[symbolName].datatype
            tc = self.getTypeCode( symbolType.np_basetype )
            c_type = self.getBaseType(tc)[0]

            try:
                setValue = int(value)
            except ValueError:
                setValue = float(value)

            self.comcmds.requestWrite(symbolAddress, c_type(setValue))

            # Todo, handle ack

            if self.workingParamSet!='':
                self.paramSet[self.workingParamSet][SET_DATA_KEY][symbolName] = setValue



    def startMeasurements(self):
        for r,p in enumerate(self.rasterPeriods):
            for name,s in self.workingSymbols.iteritems():
                if s.period_s==p:
                    self.addToRaster(r, name)
                    s.initForSampling(10)

        self.updateTargetRasters()
        self.isStarted = True

    def stopMeasurements(self):
        self.disableTargetRasters()
        self.clearRaster()
        self.isStarted = False

    def addToRaster(self, rasterIndex, symbolName):
        self.raster[rasterIndex].append(symbolName)
        tc = self.getTypeCode( self.workingSymbols[symbolName].datatype.np_basetype )
        c_type = self.getBaseType(tc)[0]
        self.rasterDataStructures[rasterIndex].append(c_type)

    def clearRaster(self, rasterIndex=None):
        if rasterIndex is None:
            for r in range(self._nbrOfRasters):
                self.raster[r] = []
                self.rasterDataStructures[r] = []
        else:
            self.raster[rasterIndex] = []
            self.rasterDataStructures[rasterIndex] = []

    def disableTargetRasters(self, rasterIndex=None):
        if rasterIndex is None:
            for r in range(self._nbrOfRasters):
                self.setTargetRaster(r, [])
        else:
            self.setTargetRaster(rasterIndex, [])

    def updateTargetRasters(self, rasterIndex=None):
        if rasterIndex is None:
            for r, rasterList in enumerate(self.raster):
                indices = [self.workingSymbols[sname].index for sname in rasterList]
                self.setTargetRaster(r, indices)
        else:
            indices = [self.workingSymbols[sname].index for sname in self.raster[rasterIndex]]
            self.setTargetRaster(rasterIndex, indices)


    def getBaseType(self, typecode):
        if typecode in self._TypeCodeTable.keys():
            return self._TypeCodeTable[typecode]
        else:
            return None

    def getTypeCode(self, fromType):
        for tc, types in self._TypeCodeTable.iteritems():
            if fromType in types:
                return tc

        return None

    def interfaceCallback(self, f):
        if f.mid in self._ID_CallBacks.keys():
            self._ID_CallBacks[f.mid](f)
        else:
            print 'ID 0x{:x} is not valid'.format(f.mid)

    def ID_Meta_Callback(self, f):
        logging.debug('Response on ID CALMEAS_ID_META')

        dataTypeStructure = [ctypes.c_uint8, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]

        numberOfMeas = f.data_size / sum(map(ctypes.sizeof, dataTypeStructure))

        if not isinstance(numberOfMeas, int):
            return

        MeasMeta = list()

        for i in range(numberOfMeas):
            MeasMeta.append( [int(x.value) for x in f.getData(dataTypeStructure)] )

        putResponseData(self._ResponseFifo, MeasMeta)


    def ID_SymbolName_Callback(self, f):
        logging.debug('Response on ID CALMEAS_ID_SYMBOL_NAME')

        name = f.FrameBytesFormatted(formatting='c', spacing='')[2:]

        putResponseData(self._ResponseFifo, name)


    def ID_SymbolDesc_Callback(self, f):
        logging.debug('Response on ID CALMEAS_ID_SYMBOL_DESC')

        desc = f.FrameBytesFormatted(formatting='c', spacing='')[2:]

        putResponseData(self._ResponseFifo, desc)

    def ID_All_Callback(self, f):
        print 'Response on ID CALMEAS_ID_ALL'

    def ID_StreamAll_Callback(self, f):
        print 'Response on ID CALMEAS_ID_STREAM_ALL'

    def ID_Raster_Callback(self, f):
        #logging.debug('Response on ID CALMEAS_ID_RASTER')
        #logging.debug(f.FrameBytesFormatted())

        rasterIndex = f.getData([ctypes.c_uint8])[0].value
        data = f.getData(self.rasterDataStructures[rasterIndex])

        for i, symbolName in enumerate(self.raster[rasterIndex]):
            val = data[i].value
            self.targetSymbols[symbolName].setValue(val)


    def ID_RasterSet_Callback(self, f):
        print 'Response on ID CALMEAS_ID_RASTER_SET'

    def ID_RasterPeriods_Callback(self, f):
        logging.debug('Response on ID CALMEAS_ID_RASTER_PERIODS')
        logging.debug(f.FrameBytesFormatted())

        dataTypeStructure = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]

        periodData = [int(x.value) for x in f.getData(dataTypeStructure)]

        putResponseData(self._ResponseFifo, periodData)

    def setTargetRaster(self, raster, indices):
        f = ComFrame()
        f.interface = CALMEAS_INTERFACE

        f.mid = CALMEAS_ID_RASTER_SET

        data = [ctypes.c_uint8(raster)]
        data.extend(map(ctypes.c_uint8, indices))
        f.setData(data)

        self._comhandler.sendFrame(f)

    def requestTargetRasterPeriods(self, timeout=1):
        self._ResponseFifo.queue.clear()

        f = ComFrame()
        f.interface = CALMEAS_INTERFACE

        f.mid = CALMEAS_ID_RASTER_PERIODS
        f.setData([])

        self._comhandler.sendFrame(f)

        try:
            logging.debug('>> Waiting for raster periods')
            periods = getResponseData(self._ResponseFifo, timeout)
        except Queue.Empty:
            raise Exception('Timeout trying to get raster periods.')
        else:
            logging.debug("<< Got it")
            self.rasterPeriods = [p/1000.0 for p in periods]

        return self.rasterPeriods

    def initializeMeasurements(self):
        # Update target symbols
        try:
            self.requestTargetSymbols()
            self.requestTargetRasterPeriods()
        except Exception, e:
            raise e

        # Inherit periods from current set of working symbols
        for name,s in self.workingSymbols.iteritems():
            if name in self.targetSymbols.keys():
                if s.period_s in self.rasterPeriods:
                    self.targetSymbols[name].setPeriod(s.period_s)
                else:
                    self.targetSymbols[name].setPeriod(0.0)

        # Set working symbols as target symbols
        self.workingSymbols = self.targetSymbols


    def requestTargetSymbols(self, timeout=1):
        targetSymbols = dict()
        streamDataStructure = list()
        self._ResponseFifo.queue.clear()

        f = ComFrame()
        f.interface = CALMEAS_INTERFACE

        f.mid = CALMEAS_ID_META
        f.setData([])

        self._comhandler.sendFrame(f)

        try:
            logging.debug('>> Waiting for meta data')
            meta = getResponseData(self._ResponseFifo, timeout)
        except Queue.Empty:
            raise Exception('Timeout trying to get meta data.')
        else:
            logging.debug("<< Got it")

        for index, symbol in enumerate(meta):
            logging.debug(">>> Loop index {}".format(index))

            s = Symbol()
            s.index = index
            c_basetype = self.getBaseType(symbol[0])[0]
            streamDataStructure.append(c_basetype)
            s.setDatatype( SymbolDataType(self.getBaseType(symbol[0])[1]) )
            s.nameAddress = symbol[1]
            s.address = symbol[2]
            s.descAddress = symbol[3]

            f.mid = CALMEAS_ID_SYMBOL_NAME
            f.setData([ctypes.c_uint8(index)])
            self._comhandler.sendFrame(f)

            try:
                logging.debug('>> Waiting for name of {}'.format(index))
                s.name = getResponseData(self._ResponseFifo, timeout)
            except Queue.Empty:
                raise Exception('Timeout trying to get symbol names.')
            else:
                logging.debug("<< Got it")

            f.mid = CALMEAS_ID_SYMBOL_DESC
            f.setData([ctypes.c_uint8(index)])
            self._comhandler.sendFrame(f)

            try:
                logging.debug('>> Waiting for description of {}'.format(index))
                s.desc = getResponseData(self._ResponseFifo, timeout)
            except Queue.Empty:
                raise Exception('Timeout trying to get symbol description.')
            else:
                logging.debug("<< Got it")

            targetSymbols[s.name] = s


        self.targetSymbols = targetSymbols
        self._streamDataStructure = streamDataStructure

        return self.targetSymbols

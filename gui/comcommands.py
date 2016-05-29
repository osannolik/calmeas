from comframe import ComFrame

import ctypes
import Queue

COM_INTERFACE = 0

COM_ID_ERROR = 0
COM_ID_WRITE_TO = 1
COM_ID_READ_FROM = 2

def putResponseData(queue, data):
    queue.put(data)

def getResponseData(queue, timeout):
    ## Shorter delay than queue.get(True, timeout)
    # t = 0
    # while t<timeout:
    #     try:
    #         data = queue.get(True, 0.001)
    #     except Queue.Empty:
    #         t += 0.001
    #         if t>=timeout:
    #             raise Queue.Empty
    #     else:
    #         return data

    return queue.get(True, timeout)

class ComCommands():
    def __init__(self, comhandler):
        self._comhandler = comhandler

        self._comhandler.enableInterface(COM_INTERFACE, self.interfaceCallback)

        # Strategy assumes response order 1,2... for requests 1,2...
        # It is the callers responsibility to check if that is valid
        self._readRequestsFifo = Queue.Queue()
        self._readResponseFifo = Queue.Queue()

    def requestRead(self, address, dataTypeStructure, responseCallback=None):
        f = ComFrame()
        f.interface = COM_INTERFACE
        f.mid = COM_ID_READ_FROM

        dataByteSize = 0
        for t in dataTypeStructure:
            dataByteSize += ctypes.sizeof(t)

        f.setData([ctypes.c_uint32(address), ctypes.c_uint16(dataByteSize)])

        self._readRequestsFifo.put([address, dataTypeStructure, responseCallback])

        self._comhandler.sendFrame(f)

    def requestWrite(self, address, data):
        f = ComFrame()
        f.interface = COM_INTERFACE
        f.mid = COM_ID_WRITE_TO

        dataByteSize = ctypes.sizeof(type(data))

        f.setData([ctypes.c_uint32(address), ctypes.c_uint16(dataByteSize), data])

        self._comhandler.sendFrame(f)

    def pollReadData(self, block=True, timeout=None):
        try:
            d = self._readResponseFifo.get(block, timeout)
        except Queue.Empty:
            return (None, None)
        else:
            return d

    def ID_Error_Callback(self, f):
        print 'Response on ID COM_ID_ERROR'

    def ID_WriteTo_Callback(self, f):
        print 'Response on ID COM_ID_WRITE_TO'

    def ID_ReadFrom_Callback(self, f):
        print 'Response on ID COM_ID_READ_FROM'

        try:
            request = self._readRequestsFifo.get_nowait()
        except Queue.Empty:
            pass
        else:
            address = request[0]
            data = f.getData(request[1])

            dataValues = list()
            for d in data:
                dataValues.append(d.value)

            self._readResponseFifo.put((address, dataValues))

            if request[2] is not None:
                request[2]((address, dataValues))
        
    def setComHandler(self, comhandler):
        self._comhandler = comhandler

    def interfaceCallback(self, f):
        if f.mid==COM_ID_ERROR:
            self.ID_Error_Callback(f)
        elif f.mid==COM_ID_WRITE_TO:
            self.ID_WriteTo_Callback(f)
        elif f.mid==COM_ID_READ_FROM:
            self.ID_ReadFrom_Callback(f)
        else:
            print 'ID 0x{:x} is not valid'.format(f.mid)
            

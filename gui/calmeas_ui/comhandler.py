from comframe import FRAME_START
from comframe import ComFrame

from threading import Thread
import Queue

import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

class ComHandler():

    def __init__(self):
        self.ResetParser()

        self._interfaces = dict()
        self._queue_rx = None
        self._queue_tx = None
        self._frameQueue_tx = Queue.Queue(1000)

    def _WaitForStart(self, b):
        if b==FRAME_START:
            self.new_frame = bytearray()
            self.new_frame.append(b)
            return self._GetHeader
        else:
            print str(b) + " is not start"
            return self._WaitForStart

    def _GetHeader(self, b):
        self.new_frame.append(b)
        return self._GetSize

    def _GetSize(self, b):
        self.new_frame.append(b)
        self.expected_data_len = int(b)
        if self.expected_data_len==0:
            self.full_frames.append(self.new_frame)
            return self._WaitForStart
        else:
            self.data_cntr = 0
            return self._GetData

    def _GetData(self, b):
        self.new_frame.append(b)
        self.data_cntr += 1
        if self.data_cntr==self.expected_data_len:
            self.full_frames.append(self.new_frame)
            return self._WaitForStart
        else:
            return self._GetData

    def ParseBytes(self, bytes):
        # Search for start byte etc
        # bytes are either partial or full or a combination of frames
        self.full_frames = list()

        for b in bytes:
            self.state_machine = self.state_machine(b)

        return self.full_frames

    def ResetParser(self):
        self.full_frames = list()
        self.state_machine = self._WaitForStart
        self.new_frame = bytearray()

    def enableInterface(self, interface, callback):
        self._interfaces[int(interface)] = callback

    def disableInterface(self, interface):
        del self._interfaces[int(interface)]

    def setByteQueue_Rx(self, queue):
        self._queue_rx = queue

    def setByteQueue_Tx(self, queue):
        self._queue_tx = queue

    def setFrameQueue_Tx(self, queue):
        self._frameQueue_tx = queue

    def handler_Rx(self, block=True, timeout=None):
        try:
            bytes = self._queue_rx.get(block, timeout)
        except Queue.Empty:
            pass
        else:

            #logging.debug("Parsing recieved bytes")
            full_frames = self.ParseBytes(bytes)

            for framebytes in full_frames:
                frame = ComFrame(framebytes)

                interface = int(frame.interface)
                if interface in self._interfaces.keys():
                    callback_handle = self._interfaces[interface]
                    if callback_handle is not None:
                        callback_handle(frame)
                    else:
                        logging.warning('Interface 0x{0:x} has no registered callback function'.format(interface))
                else:
                    logging.warning('Interface 0x{0:x} is not an enabled interface'.format(interface))

    def putFrame(self, frame):
        if self._frameQueue_tx is not None:
            #logging.debug("Putting to tx frame queue")
            self._frameQueue_tx.put(frame)
            return True
        else:
            logging.error('Please set queue for tx frames first')
            return False

    def handler_Tx(self, block=False, timeout=None):
        try:
            f = self._frameQueue_tx.get(block, timeout)
        except Queue.Empty:
            pass
        else:
            bytes = f.GetFrameBytesRaw(with_start=True)
            #logging.debug("Putting to tx byte queue")
            self._queue_tx.put(bytes)

    def sendFrame(self, frame):
        if self.putFrame(frame):
            self.handler_Tx()

class ComHandlerThread(Thread, ComHandler):
    def __init__(self):
        Thread.__init__(self, name=type(self).__name__)
        ComHandler.__init__(self)

        self.setDaemon(True)

    def run(self):
        logging.debug('Starting...')
        
        self._quit = False

        if self._queue_rx is None:
            logging.error('Please set queue for rx bytes first')
            self.stop()
        
        while not self._quit:
            try:
                self.handler_Rx(block=True, timeout=0.001)
            except Exception, e:
                logging.warning(str(e))

        logging.debug('Stopping...')

    def stop(self):
        self._quit = True



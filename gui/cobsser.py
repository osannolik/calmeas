from threading import Thread
import serial
from serial.tools.list_ports import comports
import Queue

import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

STANDARD_BAUDRATES = ['50', '75', '110', '134', '150', '200', '300', '600', '1200', 
                      '1800', '2400', '4800', '9600', '19200', '38400', '57600', '115200', 
                      '230400', '460800', '500000', '576000', '921600', '1000000', '1152000', 
                      '1500000', '2000000', '2500000', '3000000', '3500000', '4000000']
DEFAULT_BAUDRATE = '230400'
DEFAULT_BAUDRATE_IDX = STANDARD_BAUDRATES.index(DEFAULT_BAUDRATE)


def _cobs_decode(in_bytes):
    # https://bitbucket.org/cmcqueen1975/cobs-python
    out_bytes = bytearray()
    idx = 0

    if len(in_bytes) > 0:
        while True:
            length = in_bytes[idx]
            if length == 0:
                raise Exception("Zero byte found in input")
            idx += 1
            end = idx + length - 1
            copy_bytes = in_bytes[idx:end]
            if '\x00' in copy_bytes:
                raise Exception("Zero byte found in input")
            out_bytes.extend(copy_bytes)
            idx = end
            if idx > len(in_bytes):
                raise Exception("Not enough input bytes for length code")
            if idx < len(in_bytes):
                if length < 0xFF:
                    out_bytes.extend('\x00')
            else:
                break
    return out_bytes
            
def _cobs_encode(in_bytes):
    # https://bitbucket.org/cmcqueen1975/cobs-python
    final_zero = True
    out_bytes = bytearray()
    idx = 0
    search_start_idx = 0

    for in_char in in_bytes:
        if in_char == 0:
            final_zero = True
            out_bytes.append(idx - search_start_idx + 1)
            out_bytes.extend(in_bytes[search_start_idx:idx])
            search_start_idx = idx + 1
        else:
            if idx - search_start_idx == 0xFD:
                final_zero = False
                out_bytes.append('\xFF')
                out_bytes.extend(in_bytes[search_start_idx:idx+1])
                search_start_idx = idx + 1
        idx += 1
    if idx != search_start_idx or final_zero:
        out_bytes.append(idx - search_start_idx + 1)
        out_bytes.extend(in_bytes[search_start_idx:idx])

    out_bytes.append('\x00')

    return out_bytes

class Serial_Handler(Thread):
    def __init__(self, direction, ser, fifo):
        Thread.__init__(self,name='CobsSer{0}Thread'.format(direction))
        self._quit = False
        self.fifo = fifo
        self.ser = ser
        self.new_frame_cb = None
        self.direction = direction.lower()
        if self.direction not in ['tx','rx']:
            raise Exception('Direction must be tx or rx')
        
    def run(self):
        logging.debug('Starting...')
        
        self._quit = False
        
        if self.direction=='tx':
            while not self._quit:
                try:
                    d = self.fifo.get(block=True, timeout=0.1)
                except Queue.Empty:
                    continue
                else:
                    try:
                        #print 'Encoding ' + str(d)
                        encoded_data = _cobs_encode(d)
                        #print 'Result ' + str(encoded_data)

                        k = ['{:#x}']*len(encoded_data)

                        logging.debug("Writing to serial: {}".format(' '.join(k).format(*encoded_data)))
                        self.ser.write(encoded_data)
                    except Exception, e:
                       logging.warning(str(e))
                       self.ser.close()
                       self._quit = True
        else:
            rxdata = bytearray()
            while not self._quit:
                try:
                   d = bytearray(self.ser.read(1))
                except Exception, e:
                   logging.warning(e)
                   self.ser.close()
                   self._quit = True

                if d == bytearray(b'\x00'):
                    
                    try:
                        decoded_data = _cobs_decode(rxdata)
                    except Exception, e:
                        logging.warning(e)
                    else:
                        #logging.debug("Putting to rx byte queue")
                        self.fifo.put(decoded_data)
                        if self.new_frame_cb is not None:
                            self.new_frame_cb(self.fifo)

                    del rxdata[:]
                else:
                    rxdata.extend(d)

        logging.debug('Stopping...')

    def stop(self):
        self._quit = True

class CobsSer():
    def __init__(self, port = '', baudrate = DEFAULT_BAUDRATE, tx_fifo_size=0, rx_fifo_size=0):
        self.Tx_fifo = Queue.Queue(tx_fifo_size)
        self.Rx_fifo = Queue.Queue(rx_fifo_size)

        self.ser = serial.Serial()
        self.ser.port = port
        self.ser.baudrate = baudrate
        self.ser.timeout = 0.001

        self.create_threads('rx')
        self.create_threads('tx')

        self.isConnected = False
        self.use_cobs = True

    def available_ports(self):
        ports = []
        for n, (port, desc, hwid) in enumerate(sorted(comports()), 1):
            #~ sys.stderr.write('--- %-20s %s [%s]\n' % (port, desc, hwid))
            logging.debug('{:2}: {:20} {}'.format(n, port, desc))
            ports.append(port)
        return ports

    def connect(self, port = '', baudrate = ''):
        if not self.isConnected:
            if port:
                self.ser.port = port
            if baudrate:
                self.ser.baudrate = baudrate

            logging.debug('Trying to open {0} at {1}'.format(self.ser.port, self.ser.baudrate))
            try:
                self.ser.open()
            except serial.SerialException as e:
                logging.error('Could not open {0}; {1}'.format(self.ser.port, e))
            else:
                self.ser.flushInput()
                self.ser.flushOutput()
                self.flush_all()
                self.isConnected = True
                logging.debug('Opened {0}'.format(self.ser.port))
                logging.debug('Bytes in serial (Rx, Tx) buffer: ({0}, {1})'.format(self.ser.inWaiting(), self.ser.outWaiting()))

    def disconnect(self):
        if self.isConnected:
            self.stop_receive()
            self.stop_transmitt()
            try:
                self.ser.close()
            except serial.SerialException as e:
                logging.warning(e)
            else:
                self.isConnected = False
                logging.debug('Closed Serial')

    def create_threads(self, direction):
        if direction.lower()=='tx':
            self.tx_thread = Serial_Handler(direction, self.ser, self.Tx_fifo)
            self.tx_thread.setDaemon(True)
        else:
            self.rx_thread = Serial_Handler(direction, self.ser, self.Rx_fifo)
            self.rx_thread.setDaemon(True)

    def start_transmitt(self):
        if self.isConnected:
            self.create_threads('Tx')

            try:
                self.tx_thread.start()
            except Exception, e:
                logging.warning(e)

    def start_receive(self):
        if self.isConnected:
            self.create_threads('Rx')

            try:
                self.rx_thread.start()
            except Exception, e:
                logging.warning(e)

    def stop_transmitt(self):
        self.tx_thread.stop()
        self.tx_thread.join()

        del self.tx_thread

    def stop_receive(self):
        self.rx_thread.stop()
        self.rx_thread.join()

        del self.rx_thread

    def flush_all(self):
        self.Tx_fifo.queue.clear()
        self.Rx_fifo.queue.clear()

    def set_rx_callback(self, handle):
        self.rx_thread.new_frame_cb = handle




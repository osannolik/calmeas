import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

from PyQt4 import QtCore, QtGui
import csv
from datetime import datetime

class Toolbar_UI(QtGui.QToolBar):

    START_BTN_TEXT = "Start measurement"
    STOP_BTN_TEXT = "Stop measurement"
    UNINIT_BTN_TEXT = "Initialize first"
    LOG_BTN_TEXT = "Toggle logging"

    def __init__(self, parent=None):
        super(Toolbar_UI, self).__init__(parent)

        self._startIcon = QtGui.QIcon('icons/toolbar_start_icon.png')
        self._stopIcon = QtGui.QIcon('icons/toolbar_stop_icon.png')
        self._recordUncheckedIcon = QtGui.QIcon('icons/record_unchecked_icon.png')
        self._recordCheckedIcon = QtGui.QIcon('icons/record_checked_icon.png')

        self.startStop = QtGui.QAction(self._startIcon, self.UNINIT_BTN_TEXT, self)
        self.addAction(self.startStop)

        self.record = QtGui.QAction(self._recordUncheckedIcon, self.UNINIT_BTN_TEXT, self)
        self.record.setCheckable(True)
        self.addAction(self.record)

        self.setIconSize(QtCore.QSize(23,23))

class MeasController(QtGui.QWidget):

    MeasurementStarted = QtCore.pyqtSignal()
    MeasurementStopped = QtCore.pyqtSignal()

    def __init__(self, calmeas):
        QtGui.QWidget.__init__(self)

        self._calmeas = calmeas
        self.widgets = list()

        self.ui_toolbar = Toolbar_UI(self)

        self.ui_toolbar.startStop.setEnabled(False)
        self.ui_toolbar.record.setChecked(False)
        self.ui_toolbar.record.setEnabled(False)

        self.ui_toolbar.startStop.triggered.connect(self._onStartStop)
        self._isStartReady = True

        self.ui_toolbar.record.toggled.connect(self._onLog)

        self._calmeas.setUpdatedSymbolValueCallback(self._updatedSymbol)
        self._doLog = False

    def _clearLogBuffer(self):
        self._logBuffer = dict()

    def startLog(self):
        self._doLog = True
        self._clearLogBuffer()
        self._startLogTimestamp = datetime.utcnow()
        logging.debug("Starting log")

    def stopLog(self):
        self._doLog = False
        self.ui_toolbar.record.setChecked(False)
        logging.debug("Stopping log")

    def saveLogToFile(self):

        logFileDialog = QtGui.QFileDialog()
        logFileDialog.setFilter(logFileDialog.filter() | QtCore.QDir.Hidden)
        logFileDialog.setDefaultSuffix('csv')
        logFileDialog.setNameFilters(['CSV (*.csv)'])
        logFileDialog.setAcceptMode(QtGui.QFileDialog.AcceptSave)
        defaultFileName = "Log_{}".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
        logFileDialog.selectFile(defaultFileName)

        if logFileDialog.exec_() == QtGui.QDialog.Accepted:
            fname = str(logFileDialog.selectedFiles()[0])

            try:
                with open(fname, 'w') as f:
                    headerWriter = csv.writer(f, quoting=csv.QUOTE_ALL, delimiter=',')
                    writer = csv.writer(f, quoting=csv.QUOTE_NONE, delimiter=',')

                    columns = list()
                    header = list()
                    for name in self._logBuffer.keys():
                        header.extend(['{}_time'.format(name), '{}'.format(name)])
                        [time, values] = zip(*self._logBuffer[name])
                        columns.extend([time, values])
                    
                    rows = map(list,map(None,*columns)) # Transpose list of lists

                    headerWriter.writerow(tuple(header))

                    for r in rows:
                        writer.writerow(tuple(r))

            except Exception, e:
                msg = QtGui.QMessageBox()
                msg.setIcon(QtGui.QMessageBox.Warning)
                msg.setText("Save exception")
                text = "Tried to save logged data to file {0}:\n\n {1}".format(fname, str(e))
                msg.setInformativeText(text)
                msg.setWindowTitle("Exception")
                msg.setStandardButtons(QtGui.QMessageBox.Ok)
                retval = msg.exec_()

            else:
                logging.info("Saved measurement log to {}".format(fname))

    def _updatedSymbol(self, symbol):
        if self._doLog:
            newValue = symbol.getValueRaw()
            timestamp_s = symbol.getSymbolTime()

            try:
                self._logBuffer[symbol.name].append((timestamp_s, newValue))
            except Exception, e:
                self._logBuffer[symbol.name] = list()
                self._logBuffer[symbol.name].append((timestamp_s, newValue))

            #logging.debug("Logged {} = {} at t = {} ms".format(symbol.name, newValue, timestamp_s * 1000.0))

    def _onLog(self, checked):
        if checked:
            self.startLog()
            self.ui_toolbar.record.setIcon(self.ui_toolbar._recordCheckedIcon)
        else:
            self.stopLog()
            self.ui_toolbar.record.setIcon(self.ui_toolbar._recordUncheckedIcon)

    def _onStartStop(self):
        if self._isStartReady:
            self.ui_toolbar.startStop.setIcon(self.ui_toolbar._stopIcon)
            self.ui_toolbar.startStop.setText(self.ui_toolbar.STOP_BTN_TEXT)

            self._calmeas.startMeasurements()
            
            for cw in self.widgets:
                cw.start()

            self.MeasurementStarted.emit()

            self._isStartReady = False

            self._clearLogBuffer()
            self._startLogTimestamp = datetime.utcnow()

        else:
            self.ui_toolbar.startStop.setIcon(self.ui_toolbar._startIcon)
            self.ui_toolbar.startStop.setText(self.ui_toolbar.START_BTN_TEXT)

            self._calmeas.stopMeasurements()
            
            for cw in self.widgets:
                cw.stop()

            self.MeasurementStopped.emit()

            self._isStartReady = True

            self.ui_toolbar.record.setChecked(False)

            if len(self._logBuffer)>0:
                self.saveLogToFile()

    def _onStop(self):
        self.ui_toolbar.startStop.triggered.disconnect(self._onStop)
        self.ui_toolbar.startStop.triggered.connect(self._onStart)

    def enable(self):
        if self._isStartReady:
            self.ui_toolbar.startStop.setText(self.ui_toolbar.START_BTN_TEXT)
        else:
            self.ui_toolbar.startStop.setText(self.ui_toolbar.STOP_BTN_TEXT)

        self.ui_toolbar.startStop.setEnabled(True)
        self.ui_toolbar.record.setEnabled(True)
        self.ui_toolbar.record.setText(self.ui_toolbar.LOG_BTN_TEXT)

    def disable(self):
        self.ui_toolbar.startStop.setText(self.ui_toolbar.UNINIT_BTN_TEXT)
        self.ui_toolbar.startStop.setEnabled(False)
        self._isStartReady = True

        self.ui_toolbar.record.setEnabled(False)
        self.ui_toolbar.record.setChecked(False)
        self.ui_toolbar.record.setText(self.ui_toolbar.UNINIT_BTN_TEXT)

    def newVisualWidget(self, vwType, symbols=[]):
        newWidget = vwType(self, self._calmeas)
        newWidget.name = str(len(self.widgets))

        i = 0
        while newWidget.name in [cw.name for cw in self.widgets]:
            newWidget.name = str(i)
            i = i+1

        newWidget.finished.connect(lambda result, cw=newWidget: self.deleteVisualWidget(cw))
        self.widgets.append(newWidget)

        newWidget.show()

        if self._calmeas.isStarted:
            newWidget.start()

        return newWidget

    def deleteVisualWidget(self, vw):
        self.widgets.remove(vw)

    def addSymbols(self, symbolNames, vw):
        vw.addSymbols(symbolNames)


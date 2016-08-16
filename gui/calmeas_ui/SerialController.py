import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

from PyQt4 import QtCore, QtGui
from cobsser import DEFAULT_BAUDRATE

class Serial_UI(QtGui.QTabWidget):

    def __init__(self, parent=None):
        super(Serial_UI, self).__init__(parent)

        self.setMinimumSize(400, 90)

        self.hbox = QtGui.QHBoxLayout()
        self.vbox = QtGui.QVBoxLayout()
        
        self.grid = QtGui.QGridLayout()
        
        self.portLbl = QtGui.QLabel('Port', self)
        self.baudrateLbl = QtGui.QLabel('Baud', self)

        self.portCombo = QtGui.QComboBox(self)
        self.portCombo.setMinimumWidth(150)

        self.baudText = QtGui.QLineEdit(self)
        self.baudText.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp("[0-9]+"), self.baudText))
        self.baudText.setMinimumWidth(150)
        self.baudText.setText('2000000')

        self.refreshBtn = QtGui.QPushButton('Refresh', self)
        self.refreshBtn.setFixedWidth(105)

        self.connectBtn = QtGui.QPushButton('Connect', self)
        self.connectBtn.setFixedWidth(105)

        self.grid.addWidget(self.portLbl, 0, 0)
        self.grid.addWidget(self.portCombo, 0, 1)
        self.grid.addWidget(self.refreshBtn, 0, 2)
        self.grid.addWidget(self.baudrateLbl, 1, 0)
        self.grid.addWidget(self.baudText, 1, 1)
        self.grid.addWidget(self.connectBtn, 1, 2)

        self.hbox.addLayout(self.grid)
        self.hbox.addStretch()
        self.vbox.addLayout(self.hbox)
        self.vbox.addStretch()

        self.setLayout(self.vbox)


class SerialController(QtGui.QWidget):

    Connected = QtCore.pyqtSignal()
    Disconnected = QtCore.pyqtSignal()

    def __init__(self, cobsser):
        QtGui.QWidget.__init__(self)

        self._cobsser = cobsser

        self.ui = Serial_UI(self)

        self.ui.refreshBtn.clicked.connect(self._onRefreshButton)
        self.ui.connectBtn.clicked.connect(self._onConnectButton)

        self._onRefreshButton()
        
    def _onRefreshButton(self):
        selectedPort = self.ui.portCombo.currentText()

        self.ui.portCombo.clear()
        self.ui.portCombo.addItems(self._cobsser.available_ports())

        selectedPortIdx = self.ui.portCombo.findText(selectedPort)

        if selectedPortIdx >= 0:
            self.ui.portCombo.setCurrentIndex(selectedPortIdx)

    def _onConnectButton(self):
        try:
            if self.isConnected():
                self.disconnect()
            else:
                self.connect(str(self.ui.portCombo.currentText()), 
                             str(self.ui.baudText.text()))

        except Exception, e:
            msg = QtGui.QMessageBox()
            msg.setIcon(QtGui.QMessageBox.Warning)
            msg.setText("Connection exception")
            text = "Tried to connect to port {0} at baud {1}:\n\n {2}".format(
                    self.ui.portCombo.currentText(), self.baudText.text(), str(e))
            msg.setInformativeText(text)
            msg.setWindowTitle("Exception")
            msg.setStandardButtons(QtGui.QMessageBox.Ok)
            retval = msg.exec_()

        if self.isConnected():
            self.ui.connectBtn.setText('Disconnect')
            self.ui.baudText.setEnabled(False)
            self.ui.portCombo.setEnabled(False)
            self.ui.refreshBtn.setEnabled(False)
        else:
            self.ui.connectBtn.setText('Connect')
            self.ui.baudText.setEnabled(True)
            self.ui.portCombo.setEnabled(True)
            self.ui.refreshBtn.setEnabled(True)

    def onMeasurementStarted(self):
        self.ui.baudText.setEnabled(False)
        self.ui.portCombo.setEnabled(False)
        self.ui.refreshBtn.setEnabled(False)
        self.ui.connectBtn.setEnabled(False)

    def onMeasurementStopped(self):
        self.ui.connectBtn.setEnabled(True)

    def connect(self, port = [], baud = DEFAULT_BAUDRATE):
        if baud=='':
            raise Exception("Please enter baud.")

        #comhandler.ResetParser()
        self._cobsser.connect(port, baud)
        self._cobsser.start_receive()
        self._cobsser.start_transmitt()

        self.Connected.emit()

    def disconnect(self):
        sts = self._cobsser.disconnect()
        self.Disconnected.emit()
        return sts

    def isConnected(self):
        return self._cobsser.isConnected

import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

from PyQt4 import QtCore, QtGui


class Meas_UI(QtGui.QWidget):

    START_BTN_TEXT = "Start"
    STOP_BTN_TEXT = "Stop"

    def __init__(self, parent=None):
        super(Meas_UI, self).__init__(parent)

        layout = QtGui.QVBoxLayout(self)

        self.startBtn = QtGui.QPushButton(self.START_BTN_TEXT, self)
        self.startBtn.setFixedWidth(105)
        self.startBtn.setEnabled(False)

        layout.addWidget(self.startBtn, stretch=0)

        layout.setAlignment(self.startBtn, QtCore.Qt.AlignRight)
        layout.addSpacing(0)

        self.setLayout(layout)


class MeasController(QtGui.QWidget):

    MeasurementStarted = QtCore.pyqtSignal()
    MeasurementStopped = QtCore.pyqtSignal()

    def __init__(self, calmeas):
        QtGui.QWidget.__init__(self)

        self._calmeas = calmeas
        self.widgets = list()

        self.ui = Meas_UI(self)

        self.ui.startBtn.clicked.connect(self._onStartButton)

    def _onStartButton(self):
        if self.ui.START_BTN_TEXT==self.ui.startBtn.text():
            self._calmeas.startMeasurements()
            
            for cw in self.widgets:
                cw.start()

            self.ui.startBtn.setText(self.ui.STOP_BTN_TEXT)
            self.MeasurementStarted.emit()

        else:
            self._calmeas.stopMeasurements()
            
            for cw in self.widgets:
                cw.stop()

            self.ui.startBtn.setText(self.ui.START_BTN_TEXT)
            self.MeasurementStopped.emit()

    def enable(self):
        self.ui.startBtn.setEnabled(True)

    def disable(self):
        self.ui.startBtn.setEnabled(False)
        self.ui.startBtn.setText(self.ui.START_BTN_TEXT)

    def newVisualWidget(self, vwType, symbols=[]):
        newWidget = vwType(self, self._calmeas)
        newWidget.name = str(len(self.widgets))

        i = 0
        while newWidget.name in [cw.name for cw in self.widgets]:
            newWidget.name = str(i)
            i = i+1

        newWidget.finished.connect(lambda result, cw=newWidget: self.deleteVisualWidget(cw))
        #newWidget.RequestCalibration.connect(self.calibrate)
        #newWidget.ParametersRemoved.connect(self.removeSymbols)
        self.widgets.append(newWidget)

        newWidget.show()

        if self._calmeas.isStarted:
            newWidget.start()

        return newWidget

    def deleteVisualWidget(self, vw):
        self.widgets.remove(vw)

    def addSymbols(self, symbolNames, vw):
        vw.addSymbols(symbolNames)


#!/bin/env python

import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')
import sys
from PyQt4 import QtCore, QtGui
import pyqtgraph as pg

from cobsser import CobsSer

from comhandler import ComHandlerThread
from calmeas import CalMeas

from SerialController import SerialController
from SynchController import SynchController
from MeasController import MeasController
from SymbolController import SymbolController
from CalibrationController import CalibrationController

cobsser = CobsSer()
comhandler = ComHandlerThread()
calmeas = CalMeas(comhandler)


class CalMeas_UI(QtGui.QMainWindow):

    WINDOWTITLE = "Measurement and Calibration Tool"

    def __init__(self, parent=None):
        super(CalMeas_UI, self).__init__(parent)

        self.mainWidget = QtGui.QWidget(self) # dummy widget to contain the layout manager

        self.topWidget = QtGui.QWidget(self)
        self.bottomWidget = QtGui.QWidget(self)

        self.mainLayout = QtGui.QVBoxLayout(self.mainWidget)
        self.topLayout = QtGui.QHBoxLayout(self.topWidget)
        self.bottomLayout = QtGui.QVBoxLayout(self.bottomWidget)

        self.setCentralWidget(self.mainWidget)

        self.mainLayout.addWidget(self.topWidget, stretch=0)
        self.mainLayout.addWidget(self.bottomWidget, stretch=1)
        
        self.SerialController = SerialController(cobsser)
        self.MeasController = MeasController(calmeas)
        self.CalibrationController = CalibrationController(calmeas)
        self.SymbolController = SymbolController(calmeas, self.CalibrationController, self.MeasController)

        self.SynchController = SynchController(calmeas)

        #self.tabWidget = QtGui.QTabWidget(self)
        #self.tabWidget.addTab(self.MeasController.ui, "Symbols")
        self.bottomLayout.addWidget(self.SymbolController.ui)
        self.addToolBar(self.MeasController.ui_toolbar)

        self.topLayout.addWidget(self.SerialController.ui, stretch=0)
        self.topLayout.addStretch()
        self.topLayout.addWidget(self.SynchController.ui, stretch=0)

        # Signaling infrastructure
        self.SerialController.Connected.connect(self.SynchController.enableInit)
        self.SerialController.Disconnected.connect(self.SynchController.disableInit)
        self.SerialController.Disconnected.connect(self.SynchController.disableSynch)
        self.SerialController.Disconnected.connect(self.MeasController.disable)

        self.SynchController.InitializationSuccessful.connect(self.SymbolController.addSymbols)
        self.SynchController.InitializationSuccessful.connect(self.SynchController.enableSynch)

        self.SynchController.DatasetChanged.connect(self.CalibrationController.refreshAllParameters)

        self.SynchController.InitializationSuccessful.connect(self.MeasController.enable)
        self.SynchController.InitializationFailed.connect(self.MeasController.disable)
        self.SynchController.InitializationFailed.connect(self.SynchController.disableSynch)

        self.MeasController.MeasurementStarted.connect(lambda onoff=False: self.SymbolController.enablePeriodCombos(onoff))
        self.MeasController.MeasurementStopped.connect(lambda onoff=True: self.SymbolController.enablePeriodCombos(onoff))
        self.MeasController.MeasurementStarted.connect(self.SynchController.disableInit)
        self.MeasController.MeasurementStopped.connect(self.SynchController.enableInit)
        self.MeasController.MeasurementStarted.connect(self.SerialController.onMeasurementStarted)
        self.MeasController.MeasurementStopped.connect(self.SerialController.onMeasurementStopped)

        self.setWindowTitle(self.WINDOWTITLE)
        self.resize(700, 750)

def open_app():
    app = QtGui.QApplication(sys.argv)

    # Uncomment to force use of dot as the decimal separator:
    #QtCore.QLocale.setDefault( QtCore.QLocale('en_US') )

    comhandler.setByteQueue_Rx(cobsser.Rx_fifo)
    comhandler.setByteQueue_Tx(cobsser.Tx_fifo)
    comhandler.start()

    cmui = CalMeas_UI()

    app.aboutToQuit.connect(lambda cmui=cmui: on_exit(cmui))

    cmui.show()

    sys.exit(app.exec_())


def on_exit(cmui):
    if cmui.SerialController.isConnected():
        try:
            cmui.SerialController.disconnect()
        except Exception, e:
            raise e
        else:
            logging.debug('Closed Serial')

    try:
        comhandler.stop()
        comhandler.join()
    except Exception, e:
        raise e
    else:
        logging.debug('Stopped com handler thread')

if __name__ == '__main__':
    open_app()
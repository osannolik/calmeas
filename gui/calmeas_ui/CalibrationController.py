import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

from PyQt4 import QtCore, QtGui


class CalibrationController(QtGui.QWidget):

    def __init__(self, calmeas):
        QtGui.QWidget.__init__(self)

        self._calmeas = calmeas

        self.widgets = list()

    def newCalibrationWidget(self, cwType, symbols=[]):
        newWidget = cwType(self, self._calmeas)
        newWidget.name = str(len(self.widgets))

        i = 0
        while newWidget.name in [cw.name for cw in self.widgets]:
            newWidget.name = str(i)
            i = i+1

        newWidget.finished.connect(lambda result, cw=newWidget: self.deleteCalibrationWidget(cw))
        newWidget.RequestCalibration.connect(self.calibrate)
        newWidget.ParametersRemoved.connect(self.removeSymbols)
        self.widgets.append(newWidget)

        newWidget.show()

        return newWidget

    def calibrate(self, symValList):
        for symbolName, value in symValList:
            self._calmeas.setSymbolTargetValue(symbolName, value)
        self.refreshAllParameters()

    def deleteCalibrationWidget(self, cw):
        for symbolName in cw.parameters():
            cw.removeParameter(symbolName)
        try:
            self.widgets.remove(cw)
        except Exception, e:
            pass

    def addSymbols(self, symbolNames, cw):
        '''Add a symbol to the calibration widget cw'''
        for symbolName in symbolNames:
            try:
                self._calmeas.addParam(symbolName)
            except Exception, e:
                raise e
            else:
                cw.addParameter(symbolName)
                self.refreshAllParameters()

    def removeSymbols(self, symbolNames):
        for symbolName in symbolNames:
            self._calmeas.removeParam(symbolName)

    def refreshAllParameters(self):
        '''Sets all values in all widgets according to the active calmeas set'''
        setData = self._calmeas.getParamSet()
        for symbolName, value in setData.iteritems():
            for cw in self.widgets:
                cw.setValue(symbolName, value)

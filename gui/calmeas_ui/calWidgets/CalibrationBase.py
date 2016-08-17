import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

from PyQt4 import QtCore, QtGui
import abc
    
class Meta_ABC_QDialog(abc.ABCMeta, type(QtGui.QDialog)):
    pass

class CalibrationBase(QtGui.QDialog):

    __metaclass__ = Meta_ABC_QDialog

    RequestCalibration = QtCore.pyqtSignal(list)
    ParametersRemoved = QtCore.pyqtSignal(list)

    IDENT = "Calibration Widget"

    def __init__(self, parent, calmeas):
        super(CalibrationBase, self).__init__(parent)

        self._calmeas = calmeas

        self.name = ""

        self._allowReqCal = True

    def name():
        doc = "The name property."
        def fget(self):
            return self._name
        def fset(self, value):
            self._name = "{} [{}]".format(self.IDENT, value)
            self.setWindowTitle(self._name)
        def fdel(self):
            del self._name
        return locals()
    name = property(**name())


    # All calibration widgets need to implement these:

    @abc.abstractmethod
    def addParameter(self, symbolName):
        pass

    @abc.abstractmethod
    def removeParameter(self, symbolName):
        pass

    @abc.abstractmethod
    def valueSetter(self, symbolName, value):
        pass

    @abc.abstractmethod
    def parameters(self):
        '''Should return the symbol names of all parameters'''
        pass

    # Helper functions to simplify for implementing calibration widgets:

    def writeValueToTarget(self, symbolName, value):
        '''This should be used when requesting a value to be sent to target'''
        if self._allowReqCal:
            if self.getSymbolDatatype(symbolName).isInteger():
                value = int(value)
                
            self.RequestCalibration.emit([(symbolName, value)])

    def setValue(self, symbolName, value):
        '''This is used to set a value in the widget but does 
           NOT result in anything being written to target'''
        self._allowReqCal = False
        try:
            self.valueSetter(symbolName, value)
        except Exception, e:
            pass
        self._allowReqCal = True

    def getSymbolDatatype(self, symbolName):
        '''A helper for getting the datatype of a symbol'''
        return self.getSymbol(symbolName).datatype

    def getSymbolDesc(self, symbolName):
        '''A helper for getting the description text of a symbol'''
        return self.getSymbol(symbolName).desc

    def getSymbol(self, symbolName):
        '''A helper for getting the actual symbol object'''
        try:
            return self._calmeas.workingSymbols[symbolName]
        except Exception, e:
            Exception("Does {} really exist as a symbol?".format(symbolName))

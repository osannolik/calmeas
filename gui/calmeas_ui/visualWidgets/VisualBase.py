import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

from PyQt4 import QtCore, QtGui
import abc
    
class Meta_ABC_QDialog(abc.ABCMeta, type(QtGui.QDialog)):
    pass

class VisualBase(QtGui.QDialog):

    __metaclass__ = Meta_ABC_QDialog

    SymbolsRemoved = QtCore.pyqtSignal(list)

    IDENT = "Visualization Widget"

    def __init__(self, parent, calmeas):
        super(VisualBase, self).__init__(parent)

        self._calmeas = calmeas

        self.name = ""

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


    # All visualization widgets need to implement these:

    @abc.abstractmethod
    def addSymbols(self, symbolNames):
        pass

    @abc.abstractmethod
    def removeSymbols(self, symbolNames):
        pass

    @abc.abstractmethod
    def start(self):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    @abc.abstractmethod
    def symbols(self):
        '''Should return the symbol names of all symbols'''
        pass


    # Helper functions to simplify for implementing visualization widgets:

    def getSymbolData(self, symbolName):
        '''A helper for getting the data buffer of a symbol'''
        return self.getSymbol(symbolName).data

    def getSymbolTime(self, symbolName):
        '''A helper for getting the time buffer of a symbol'''
        return self.getSymbol(symbolName).time

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

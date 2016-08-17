import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

from PyQt4 import QtCore, QtGui

from visualWidgets.VisualBase import VisualBase


class MeasTable(VisualBase):

    IDENT = "Measurement Table"

    HEADER = ("Symbol", "Value")
    MENU_REMOVE_TEXT = "Remove"
    MENU_SHOW_TEXT = "Show as"
    MENU_HEX_TEXT = "Hex"
    MENU_DEC_TEXT = "Dec"

    def __init__(self, parent, calmeas):
        super(MeasTable, self).__init__(parent, calmeas)

        splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        layout = QtGui.QVBoxLayout()
        layout.setMargin(0)

        self.tree = QtGui.QTreeWidget(self)
        self.tree.setRootIsDecorated(False)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._openMenu)
        self.tree.setColumnCount( len(self.HEADER) )
        self.tree.setHeaderLabels( self.HEADER )
        self.tree.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)

        layout.addWidget(self.tree)
        self.setLayout(layout)

        self.resize(600, 300)

        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.update)

        self.updateInterval = 100

    def addSymbols(self, symbolNames):
        for symbolName in symbolNames:
            if symbolName not in self.symbols():
                item = MeasTableItem(self, symbolName)
                item.setToolTip(0, self.getSymbolDesc(symbolName))
                if self._calmeas.isStarted:
                    item.enable()

    def removeSymbols(self, symbolNames):
        root = self.tree.invisibleRootItem()
        for item in self._items():
            if item.symbolName in symbolNames:
                item.disable()
                root.removeChild(item)

    def start(self):
        for item in self._items():
            item.enable()
        self._timer.start(self.updateInterval)

    def stop(self):
        self._timer.stop()

    def update(self):
        for item in self._items():
            item.updateValue()

    def symbols(self):
        return [item.symbolName for item in self._items()]

    def _items(self):
        items = list()
        iterator = QtGui.QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            items.append(iterator.value())
            iterator += 1
        return items

    def _openMenu(self, position):
        items = self.tree.selectedItems()
        symbolNames = [item.symbolName for item in items]

        menu = QtGui.QMenu()

        submenuShow = QtGui.QMenu(self.MENU_SHOW_TEXT)

        sa = submenuShow.addAction(self.MENU_DEC_TEXT)
        sa.triggered.connect(lambda checked, symbolNames=symbolNames: self._showDec(symbolNames))
        sa = submenuShow.addAction(self.MENU_HEX_TEXT)
        sa.triggered.connect(lambda checked, symbolNames=symbolNames: self._showHex(symbolNames))

        menu.addMenu(submenuShow)

        action = menu.addAction(self.MENU_REMOVE_TEXT)
        action.triggered.connect(lambda checked, symbolNames=symbolNames: self.removeSymbols(symbolNames))

        if items:
            a = menu.exec_(self.tree.viewport().mapToGlobal(position))

    def _showHex(self, symbolNames):
        for item in self._items():
            if item.symbolName in symbolNames and self.getSymbolDatatype(item.symbolName).isInteger():
                item.setHex(True)

    def _showDec(self, symbolNames):
        for item in self._items():
            if item.symbolName in symbolNames:
                item.setHex(False)

class MeasTableItem( QtGui.QTreeWidgetItem ):

    def __init__( self, measTable, symbolName ):
        super(MeasTableItem, self).__init__(measTable.tree)

        self.measTable = measTable
        self.symbolName = symbolName
        self.setText(0, symbolName)

        self._enabled = False
        self._showHex = False

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def setHex(self, onoff):
        self._showHex = onoff

    def showHex(self):
        return self._showHex

    def updateValue(self):
        if self._enabled:
            try:
                valStr = self.measTable.getSymbol(self.symbolName).getValueStr()
            except Exception, e:
                valStr = ""

            try:
                valRaw = self.measTable.getSymbol(self.symbolName).getValueRaw()
                valHexStr = "0x{:x}".format(valRaw)
            except Exception, e:
                valHexStr = ""

            if self._showHex:
                self.setText(1, valHexStr)
                self.setToolTip(1, valStr)
            else:
                self.setText(1, valStr)
                self.setToolTip(1, valHexStr)

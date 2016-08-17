import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

from PyQt4 import QtCore, QtGui

from calWidgets.CalibrationBase import CalibrationBase


class CalibrationTable(CalibrationBase):

    IDENT = "Calibration Table"

    TREE_HEADER = ("Symbol", "Value", "Type", "Description")
    MENU_REMOVE_TEXT = "Remove"

    def __init__(self, parent, calmeas):
        super(CalibrationTable, self).__init__(parent, calmeas)

        self.layout = QtGui.QVBoxLayout()
        self.layout.setMargin(0)

        self.tree = QtGui.QTreeWidget(self)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._openMenu)
        self.tree.setColumnCount( len(self.TREE_HEADER) )
        self.tree.setHeaderLabels( self.TREE_HEADER )

        self.layout.addWidget(self.tree)

        self.setLayout(self.layout)

        self.resize(600, 300)

    def addParameter(self, symbolName):
        if symbolName not in self.parameters():
            cti = CalibrationTableItem(self, symbolName)
            for column in range( self.tree.columnCount() ):
                self.tree.resizeColumnToContents( column )
            self.tree.header().resizeSection(1, 90)

    def valueSetter(self, symbolName, value):
        setToItems = [item for item in self._items() if item.symbolName==symbolName]

        for item in setToItems:
            item.valueSetter(value)

    def removeParameter(self, symbolName):
        removed = list()
        root = self.tree.invisibleRootItem()
        for item in self._items():
            if item.symbolName==symbolName:
                root.removeChild(item)
                removed.append(symbolName)

        self.ParametersRemoved.emit(removed)

    def parameters(self):
        return [item.symbolName for item in self._items()]

    def _removeParameterItems(self, items):
        for item in items:
            self.removeParameter(item.symbolName)

    def _openMenu(self, position):
        items = self.tree.selectedItems()

        self.menu = QtGui.QMenu()
        action = self.menu.addAction(self.MENU_REMOVE_TEXT)
        action.triggered.connect(lambda checked, items=items: self._removeParameterItems(items))

        if items:
            a = self.menu.exec_(self.tree.viewport().mapToGlobal(position))

    def _items(self):
        items = list()
        iterator = QtGui.QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            items.append(iterator.value())
            iterator += 1
        return items

class CalibrationTableItem(QtGui.QTreeWidgetItem):

    def __init__(self, calTable, symbolName):

        super(CalibrationTableItem, self).__init__(calTable.tree)

        self.symbolName = symbolName

        self._calTable = calTable

        self.setText(0, symbolName)

        datatype = self._calTable.getSymbolDatatype(symbolName)
        self.setText(2, datatype.text)

        self.valueEditor = QtGui.QDoubleSpinBox()

        if datatype.isInteger():
            self.valueEditor.setDecimals(0)

        minVal, maxVal = datatype.range()
        self.valueEditor.setRange(minVal, maxVal)
        self.valueEditor.setKeyboardTracking(False)
        self.valueEditor.valueChanged.connect(self.valueChanged)
        self.treeWidget().setItemWidget(self, 1, self.valueEditor)
        
        self.setText(3, self._calTable.getSymbolDesc(self.symbolName))

    def valueChanged(self, val):
        self._calTable.writeValueToTarget(self.symbolName, val)

    def valueSetter(self, value):
        self.valueEditor.setValue(value)


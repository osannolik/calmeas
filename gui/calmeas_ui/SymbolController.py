import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

from PyQt4 import QtCore, QtGui

from os import listdir
from os.path import isdir, join
import importlib

class Symbol_UI(QtGui.QWidget):

    TREE_HEADER = ("Symbol", "Type", "Period [s]", "Description")

    def __init__(self, parent=None):
        super(Symbol_UI, self).__init__(parent)

        layout = QtGui.QVBoxLayout(self)
        
        self.tree = QtGui.QTreeWidget(self)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        self.tree.setColumnCount( len(self.TREE_HEADER) )
        self.tree.setHeaderLabels( self.TREE_HEADER )
        self.tree.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)

        layout.addWidget(self.tree, stretch=1)

        layout.addSpacing(0)

        self.setLayout(layout)

def _importCalVisWidgetClasses(folder):
    widgetClasses = dict()

    widgetNames = [f for f in listdir(folder) if isdir(join(folder, f))]
    
    for widgetName in widgetNames:
        try:
            # Widget package, module and class all need to be named the same thing...
            module = importlib.import_module("{0}.{1}.{1}".format(folder, widgetName))
            classInstance = getattr(module, widgetName)
        except Exception, e:
            logging.error('Problem importing {}'.format(widgetName))
        else:
            widgetClasses[widgetName] = classInstance

    return widgetClasses


class SymbolController(QtGui.QWidget):

    CALWIDGETS_DIR = "calWidgets"
    VISWIDGETS_DIR = "visualWidgets"

    def __init__(self, calmeas, calctrl, measctrl):
        QtGui.QWidget.__init__(self)

        self._calmeas = calmeas
        self._calctrl = calctrl
        self._measctrl = measctrl

        self.ui = Symbol_UI()

        self.ui.tree.customContextMenuRequested.connect(self._openMenu)

        self.calWidgetClasses = _importCalVisWidgetClasses(self.CALWIDGETS_DIR)
        self.visualWidgetClasses = _importCalVisWidgetClasses(self.VISWIDGETS_DIR)

    def addSymbols(self):
        self.ui.tree.clear()
        for symbolName, symbol in sorted(self._calmeas.workingSymbols.items(), key=lambda kv: kv[0]):
            item = SymbolTreeItem( self.ui.tree, symbol, self._calmeas.rasterPeriods )
            item.periodCombo.currentIndexChanged.connect(lambda index, name=symbolName, combo=item.periodCombo: self._updatedPeriod(name, combo))
            for column in range( self.ui.tree.columnCount() ):
                self.ui.tree.resizeColumnToContents( column )

    def _updatedPeriod(self, name, combo):
        try:
            per = float(str(combo.currentText()))
        except:
            self._calmeas.workingSymbols[name].setPeriod( 0.0 )
        else:
            self._calmeas.workingSymbols[name].setPeriod( per )

    def moveToPeriod(self, checked, period):
        for item in self.ui.tree.selectedItems():
            self._updatedPeriod(item.symbolName, item.periodCombo)
            indexToPeriod = item.periodCombo.findText(str(period))
            item.periodCombo.setCurrentIndex(indexToPeriod)

    def _openMenu(self, position):
        selItems = self.ui.tree.selectedItems()
        if selItems:
            menu = QtGui.QMenu()

            # Submenu for period manipulation
            if not self._calmeas.isStarted:
                self.submenuPeriod = QtGui.QMenu("Period")
                sa = self.submenuPeriod.addAction("Off")
                sa.triggered.connect(lambda checked, p="Off": self.moveToPeriod(checked, p))

                for p in self._calmeas.rasterPeriods:
                    sa = self.submenuPeriod.addAction("{} ms".format(p))
                    sa.triggered.connect(lambda checked, p=p: self.moveToPeriod(checked, p))

                menu.addMenu(self.submenuPeriod)

            # Submenu for adding symbol to widget
            self.submenuAdd = QtGui.QMenu("Add to")

            for visClass in self.visualWidgetClasses.values():
                sa = self.submenuAdd.addAction("New {}".format(visClass.IDENT))
                sa.triggered.connect(lambda checked, visClass=visClass: self.createNewVisWidget(visClass))

            for cwClass in self.calWidgetClasses.values():
                sa = self.submenuAdd.addAction("New {}".format(cwClass.IDENT))
                sa.triggered.connect(lambda checked, cwClass=cwClass: self.createNewCalWidget(cwClass))

            self.submenuAdd.addSeparator()

            for vw in self._measctrl.widgets:
                sa = self.submenuAdd.addAction( vw.name )
                sa.triggered.connect(lambda checked, vw=vw: self.addSelectedToVisWidget(vw))

            for cw in self._calctrl.widgets:
                sa = self.submenuAdd.addAction( cw.name )
                sa.triggered.connect(lambda checked, cw=cw: self.addSelectedToCalWidget(cw))

            menu.addMenu(self.submenuAdd)

            menu.exec_(self.ui.tree.viewport().mapToGlobal(position))

    def createNewCalWidget(self, cwClass):
        cw = self._calctrl.newCalibrationWidget(cwClass)
        self.addSelectedToCalWidget(cw)

    def addSelectedToCalWidget(self, cw):
        symbolNames = [item.symbolName for item in self.ui.tree.selectedItems()]
        self._calctrl.addSymbols(symbolNames, cw)

    def createNewVisWidget(self, visClass):
        vw = self._measctrl.newVisualWidget(visClass)
        self.addSelectedToVisWidget(vw)

    def addSelectedToVisWidget(self, vw):
        symbolNames = [item.symbolName for item in self.ui.tree.selectedItems()]
        self._measctrl.addSymbols(symbolNames, vw)

    def enablePeriodCombos(self, onoff):
        iterator = QtGui.QTreeWidgetItemIterator(self.ui.tree)
        while iterator.value():
            item = iterator.value()
            item.periodCombo.setEnabled(onoff)
            iterator += 1

class SymbolTreeItem( QtGui.QTreeWidgetItem ):

    def __init__( self, parent, symbol, rasterPeriods):

        super( SymbolTreeItem, self ).__init__( parent )

        self.symbolName = symbol.name

        self.setText( 0, symbol.name )
        self.setText( 1, symbol.datatype.text )

        self.periodCombo = QtGui.QComboBox()
        self.periodCombo.addItem("Off")
        self.periodCombo.addItems(map(str, rasterPeriods))
        self.treeWidget().setItemWidget( self, 2, self.periodCombo )

        indexToPeriod = self.periodCombo.findText(str(symbol.period_s))
        if indexToPeriod>=0:
            self.periodCombo.setCurrentIndex(indexToPeriod)
        else:
            self.periodCombo.setCurrentIndex(0)

        self.setText( 3, symbol.desc )

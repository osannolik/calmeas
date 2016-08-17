import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

from PyQt4 import QtCore, QtGui

from datetime import datetime
import copy
import json


class Synch_UI(QtGui.QWidget):

    def __init__(self, parent=None):
        super(Synch_UI, self).__init__(parent)

        self.hbox = QtGui.QHBoxLayout()
        self.hbox.addStretch()
        self.vbox = QtGui.QVBoxLayout()

        self.InitBtn = QtGui.QPushButton('Initialize', self)
        self.InitBtn.setFixedWidth(105)
        self.InitBtn.setEnabled(False)

        self.SynchBtn = QtGui.QPushButton('Datasets', self)
        self.SynchBtn.setFixedWidth(105)
        self.SynchBtn.setEnabled(False)

        self.vbox.addStretch()
        self.vbox.addWidget(self.InitBtn)
        self.vbox.addWidget(self.SynchBtn)

        self.hbox.addLayout(self.vbox)

        self.setLayout(self.hbox)


class Period_diag(QtGui.QDialog):

    def __init__(self, parent=None, oldPeriods=[], newPeriods=[]):
        super(Period_diag, self).__init__(parent)

        self.setWindowTitle("Period Mapping")

        self._oldPeriodsUnique = list( set(oldPeriods).difference(set(newPeriods)) )

        self.PeriodMapping = {0.0: 0.0}
        for p in list( set(oldPeriods).intersection(set(newPeriods)) ):
            self.PeriodMapping[p] = p

        layout = QtGui.QVBoxLayout()

        gridLayout = QtGui.QGridLayout()
    
        gridLayout.addWidget(QtGui.QLabel("Used Period", self), 0, 0)
        gridLayout.addWidget(QtGui.QLabel("Target Period", self), 0, 2)

        self._combos = dict()

        for n,op in enumerate(self._oldPeriodsUnique):
            gridLayout.addWidget(QtGui.QLabel("->", self), n+1, 1)
            gridLayout.addWidget(QtGui.QLabel(str(op), self), n+1, 0)
            combo = QtGui.QComboBox(self)
            combo.setFixedWidth(105)
            combo.addItems(map(str,newPeriods))
            gridLayout.addWidget(combo, n+1, 2)
            self._combos[str(op)] = combo

        layout.addLayout(gridLayout)

        buttonBox = QtGui.QDialogButtonBox()
        buttonBox.setOrientation(QtCore.Qt.Horizontal)
        buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Ok)

        layout.addStretch()
        layout.addWidget(buttonBox)

        self.setLayout(layout)

        self.setFixedSize(300, 200)

        buttonBox.button(QtGui.QDialogButtonBox.Ok).clicked.connect(self._returnMapping)

    def _returnMapping(self):
        for op in self._oldPeriodsUnique:
            self.PeriodMapping[op] = float( self._combos[str(op)].currentText() )

        self.accept()


class Synch_diag(QtGui.QDialog):

    def __init__(self, calmeas, parent=None):
        super(Synch_diag, self).__init__(parent)

        self.setWindowTitle("Synchronization Manager")

        self.sm = SynchManager(calmeas, self)
        self.selectedSet = None

        self.layout = QtGui.QVBoxLayout()
        self.layout.addWidget(self.sm)

        buttonBox = QtGui.QDialogButtonBox()
        buttonBox.setOrientation(QtCore.Qt.Horizontal)
        buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel | QtGui.QDialogButtonBox.Ok)

        self.layout.addWidget(buttonBox)

        self.setLayout(self.layout)

        buttonBox.button(QtGui.QDialogButtonBox.Ok).clicked.connect(self._returnSet)
        buttonBox.button(QtGui.QDialogButtonBox.Cancel).clicked.connect(self._cancel)

        self.resize(800, 500)

    def _returnSet(self):
        self.selectedSet = self.sm._returnSet()
        self.accept()

    def _cancel(self):
        self.selectedSet = None
        self.reject()

class SynchManager(QtGui.QWidget):

    TREE_HEADER = ("Name", "Target value", "Set value")
    DATASET_TEXT = "Dataset"
    COMPARISON_TEXT = "Value comparison"
    CHBOX_SET_TEXT = "Download dataset"
    CHBOX_SET_DESC = "Download the selected dataset to target"
    CHBOX_TARGET_TEXT = "Use target values"
    CHBOX_TARGET_DESC = "Create a new dataset based on the current target values"
    TOOLTIP_NOTFOUND = "Symbol not found on target"

    def __init__(self, calmeas, parent=None):
        super(SynchManager, self).__init__(parent)

        self._calmeas = calmeas

        self._cachedTargetValues = dict()

        self.initGui()

        self.setIcon = QtGui.QIcon('icons/dset_icon.png')
        self.usedSetIcon = QtGui.QIcon('icons/dset_used_icon.png')

        self.impExpDialog = QtGui.QFileDialog()
        self.impExpDialog.setFilter(self.impExpDialog.filter() | QtCore.QDir.Hidden)
        self.impExpDialog.setDefaultSuffix('json')
        self.impExpDialog.setNameFilters(['JSON (*.json)'])

        self.addDatasets()

    def initGui(self):
        layout = QtGui.QVBoxLayout()

        splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)

        leftWidget = QtGui.QWidget(self)
        leftLayout = QtGui.QVBoxLayout(leftWidget)
        leftLayout.setMargin(0)

        self.dataSetList = QtGui.QListWidget(self)
        self.dataSetList.itemSelectionChanged.connect(self.setSelected)
        self.dataSetList.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.dataSetList.customContextMenuRequested.connect(self._openSetMenu)

        leftLayout.addWidget(QtGui.QLabel(self.DATASET_TEXT, self))
        leftLayout.addWidget(self.dataSetList)

        rightWidget = QtGui.QWidget(self)
        rightLayout = QtGui.QVBoxLayout(rightWidget)
        rightLayout.setMargin(0)

        self.symTree = QtGui.QTreeWidget(self)
        self.symTree.setColumnCount( len(self.TREE_HEADER) )
        self.symTree.setHeaderLabels( self.TREE_HEADER )
        self.symTree.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.symTree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.symTree.customContextMenuRequested.connect(self._openParamMenu)

        rightLayout.addWidget(QtGui.QLabel(self.COMPARISON_TEXT, self))
        rightLayout.addWidget(self.symTree)

        splitter.addWidget(leftWidget)
        splitter.addWidget(rightWidget)
        splitter.setCollapsible(0,False)
        splitter.setCollapsible(1,False)

        layout.addWidget(splitter)

        self.chBoxSet = QtGui.QCheckBox(self.CHBOX_SET_TEXT)
        self.chBoxSet.setToolTip(self.CHBOX_SET_DESC)
        self.chBoxSet.setChecked(True)
        self.chBoxTarget = QtGui.QCheckBox(self.CHBOX_TARGET_TEXT)
        self.chBoxTarget.setToolTip(self.CHBOX_TARGET_DESC)
        self.chBoxTarget.setChecked(False)

        self.chbGroup = QtGui.QButtonGroup()
        self.chbGroup.addButton(self.chBoxSet)
        self.chbGroup.addButton(self.chBoxTarget)
        self.chbGroup.setExclusive(True)
        self.chbGroup.buttonClicked.connect(self._chBoxClicked)

        layout.addWidget(self.chBoxSet)
        layout.addWidget(self.chBoxTarget)

        self.setLayout(layout)

    def _chBoxClicked(self, chb):
        pass


    def setSelected(self):
        self.updateSymTree()


    def updateSymTree(self):
        try:
            paramSet = self._calmeas.getParamSet( str(self.dataSetList.currentItem().text()) )
        except Exception, e:
            return

        self.symTree.clear()

        for name, val in sorted(paramSet.items(), key=lambda kv: kv[0]):
            # Get corresponding target value
            try:
                targetVal = self._cachedTargetValues[name]
            except Exception, e:
                try:
                    self._cachedTargetValues[name] = self._calmeas.getSymbolTargetValue(name)[0]
                    targetVal = self._cachedTargetValues[name]
                except Exception, e:
                    targetVal = None

            # Create tree item and apply formatting
            item = QtGui.QTreeWidgetItem(self.symTree)
            item.setText( 0, name )
            item.setText( 2, str(val) )

            try:
                symbol = self._calmeas.workingSymbols[name]
                item.setText( 1, symbol.getValueStr(self._cachedTargetValues[name]) )
                toolTip = symbol.desc
            except Exception, e:
                item.setText( 1, "" )
                toolTip = self.TOOLTIP_NOTFOUND

            for column in range(self.symTree.columnCount()):
                item.setToolTip(column, toolTip)

            if targetVal != val:
                item.setBackgroundColor(1, QtGui.QColor(255, 0, 0, 100))

        for column in range(self.symTree.columnCount()):
            self.symTree.resizeColumnToContents(column)

    def _returnSet(self):
        if self.chBoxTarget.isChecked():

            currentParamStatus = [(symbol.name, symbol.isParameter) for symbol in self._calmeas.workingSymbols.values()]
            newSetDiag = NewDataset_diag(self, currentParamStatus)
            OK = newSetDiag.exec_()

            if OK:
                selectedSet = newSetDiag.setName
                self._calmeas.newParamSet(selectedSet)

                for symbolName, isParameter in newSetDiag.selectedSymbols:
                    if isParameter:
                        self._calmeas.addParam(symbolName, toSet=selectedSet)

            else:
                return None

        else:
            try:
                selectedSet = str(self.dataSetList.currentItem().text())
            except Exception, e:
                return None

        self._calmeas.useParamSet(selectedSet)

        
    def addDatasets(self):
        prevItems = list()
        for i in range(self.dataSetList.count()):
            prevItems.append(self.dataSetList.item(i).text())

        self.dataSetList.clear()

        # Todo: Better sorting...
        for setName, setData in sorted(self._calmeas.paramSet.items(), key=lambda kv: kv[0]):
            item = QtGui.QListWidgetItem(self.setIcon, setName, self.dataSetList)
            if setName == self._calmeas.workingParamSet:
                item.setIcon(self.usedSetIcon)

        newItems = [self.dataSetList.item(i) for i in range(self.dataSetList.count()) if self.dataSetList.item(i).text() not in prevItems]

        if newItems:
            self.dataSetList.setCurrentItem(newItems[0])
        elif self.dataSetList.count()>0:
            self.dataSetList.setCurrentItem(self.dataSetList.item(self.dataSetList.count() - 1))

        if self.dataSetList.count()==0:
            self.chBoxSet.setEnabled(False)
            self.chBoxTarget.setChecked(True)
            self.symTree.clear()
        else:
            self.chBoxSet.setEnabled(True)

    def _openSetMenu(self, position):
        selItems = self.dataSetList.selectedItems()

        menu = QtGui.QMenu()     
            
        if len(selItems)==1:        
            sa = menu.addAction("Duplicate...")
            sa.triggered.connect(self.newDataSet)
            menu.addSeparator()

        if len(selItems)>=1:
            sa = menu.addAction("Delete")
            sa.triggered.connect(self.delDataSet)
            sa = menu.addAction("Export...")
            sa.triggered.connect(self.expDataSet)
            menu.addSeparator()
        
        sa = menu.addAction("Import...")
        sa.triggered.connect(self.impDataSet)
        a = menu.exec_(self.dataSetList.viewport().mapToGlobal(position))

    def newDataSet(self):
        selectedSet = self.dataSetList.currentItem()
        if selectedSet is None:
            selectedSet = ''
        else:
            selectedSet = str(selectedSet.text())

        newSetName = ''
        OK = True
        while not self._validSetName(newSetName) and OK:
            newSetName, OK = QtGui.QInputDialog.getText(self, 'New Data Set', 'Please provide a name:', text=selectedSet)

        if OK:
            self._calmeas.newParamSet(str(newSetName), fromSet = selectedSet)
            self.addDatasets()

    def _validSetName(self, name):
        if name!='':
            return True
        else:
            return False

    def delDataSet(self):
        for selItem in self.dataSetList.selectedItems():
            try:
                self._calmeas.deleteParamSet(str(selItem.text()))
            except:
                pass
            else:
                self.dataSetList.takeItem(self.dataSetList.row(selItem))

        self.addDatasets()

    def impDataSet(self):
        self.impExpDialog.setAcceptMode(QtGui.QFileDialog.AcceptOpen)

        if self.impExpDialog.exec_() == QtGui.QDialog.Accepted:
            fname = str(self.impExpDialog.selectedFiles()[0])
            
            with open(fname) as f:
                data = json.load(f)

                for setName, setData in data.iteritems():
                    self._calmeas.importParamSet(setName, setData)
                
                self.addDatasets()

    def expDataSet(self):
        selItems = self.dataSetList.selectedItems()

        seldSets = dict()
        for itm in selItems:
            setName = str(itm.text())
            seldSets[setName] = self._calmeas.paramSet[setName]

        self.impExpDialog.selectFile(seldSets.keys()[0])
        self.impExpDialog.setAcceptMode(QtGui.QFileDialog.AcceptSave)

        if self.impExpDialog.exec_() == QtGui.QDialog.Accepted:
            fname = str(self.impExpDialog.selectedFiles()[0])
            with open(fname, 'w') as f:
                json.dump(seldSets, f, indent=4, sort_keys=True)

    def _openParamMenu(self, position):
        if len(self.dataSetList.selectedItems())>0:
            menu = QtGui.QMenu()     
            
            dataSet = str(self.dataSetList.selectedItems()[0].text())
            selectedSymbolNames = [str(item.text(0)) for item in self.symTree.selectedItems()]

            sa = menu.addAction("Add...")
            sa.triggered.connect(lambda checked, ds=dataSet: self._addSymbolToSet(ds))
            sa = menu.addAction("Remove")
            sa.triggered.connect(lambda checked, ds=dataSet, sn=selectedSymbolNames: self._removeSymbolsFromSet(ds, sn))

            a = menu.exec_(self.symTree.viewport().mapToGlobal(position))    

    def _addSymbolToSet(self, dataSet):
        symbols = [(symbol.name, False) for symbol in self._calmeas.workingSymbols.values()]
        addParamDiag = AddParam_diag(self, symbols)
        OK = addParamDiag.exec_()

        if OK:
            for symbolName, isParameter in addParamDiag.selectedSymbols:
                if isParameter:
                    self._calmeas.addParam(symbolName, toSet=dataSet)

            self.addDatasets()

    def _removeSymbolsFromSet(self, dataSet, symbolNames):
        for symbolName in symbolNames:
            self._calmeas.removeParam(symbolName, fromSet=dataSet)
        
        self.addDatasets()

class NewDataset_diag(QtGui.QDialog):

    WINDOWTITLE = "Create new dataset"
    NAME_TEXT = "Name"
    SYMBOLS_TEXT = "Symbols"
    NAME_DFT_TEMPLATE = "Target_{}"

    def __init__(self, parent=None, symbolNames=list(), setName=True):
        super(NewDataset_diag, self).__init__(parent)

        self.setWindowTitle(self.WINDOWTITLE)

        layout = QtGui.QVBoxLayout()

        if setName:
            layout.addWidget(QtGui.QLabel(self.NAME_TEXT, self))

            dftSetName = self.NAME_DFT_TEMPLATE.format(datetime.now().strftime("%Y%m%d_%H%M%S"))
            self.nameEditor = QtGui.QLineEdit(dftSetName, self)
            layout.addWidget(self.nameEditor)

        layout.addWidget(QtGui.QLabel(self.SYMBOLS_TEXT, self))

        self.list = QtGui.QListWidget(self)
        layout.addWidget(self.list)

        buttonBox = QtGui.QDialogButtonBox()
        buttonBox.setOrientation(QtCore.Qt.Horizontal)
        buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel | QtGui.QDialogButtonBox.Ok)
        layout.addWidget(buttonBox)

        self.setLayout(layout)

        self.setFixedSize(400, 500)

        buttonBox.button(QtGui.QDialogButtonBox.Ok).clicked.connect(self._ok)
        buttonBox.button(QtGui.QDialogButtonBox.Cancel).clicked.connect(self._cancel)

        for name, isParameter in sorted(symbolNames, key=lambda kv: kv[0]):
            item = QtGui.QListWidgetItem(name, self.list)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            if isParameter:
                item.setCheckState(QtCore.Qt.Checked)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)

    def _ok(self):
        self.selectedSymbols = []
        model = self.list.model()
        for index in xrange(self.list.count()):
            item = self.list.item(index)
            self.selectedSymbols.append( (str(item.text()), item.checkState()==QtCore.Qt.Checked) )
        
        try:
            self.setName = str(self.nameEditor.text())
        except Exception, e:
            self.setName = ""
        
        self.accept()

    def _cancel(self):
        self.selectedSymbols = []
        self.setName = ""
        self.reject()

class AddParam_diag(NewDataset_diag):

    WINDOWTITLE = "Add a new symbol"

    def __init__(self, parent=None, symbolNames=list()):
        super(AddParam_diag, self).__init__(parent, symbolNames, False)

class symTreeItem( QtGui.QTreeWidgetItem ):

    def __init__( self, parent, symbol, targetVal):
        super( symTreeItem, self ).__init__( parent )
        self.setText( 0, symbol.name )
        self.setText( 1, symbol.getValueStr(targetVal) )
        self.setText( 2, symbol.getValueStr(targetVal) )

class SynchController(QtGui.QWidget):

    InitializationSuccessful = QtCore.pyqtSignal()
    InitializationFailed = QtCore.pyqtSignal()
    DatasetChanged = QtCore.pyqtSignal()

    def __init__(self, calmeas):
        QtGui.QWidget.__init__(self)

        self._calmeas = calmeas

        self.ui = Synch_UI(self)
        
        self.ui.InitBtn.clicked.connect(self._onInitButton)
        self.ui.SynchBtn.clicked.connect(self._onSynchButton)

    def enableInit(self):
        self.ui.InitBtn.setEnabled(True)

    def disableInit(self):
        self.ui.InitBtn.setEnabled(False)

    def enableSynch(self):
        self.ui.SynchBtn.setEnabled(True)

    def disableSynch(self):
        self.ui.SynchBtn.setEnabled(False)

    def _onSynchButton(self):
        prevSet = self._calmeas.workingParamSet

        self.synchDialog = Synch_diag(self._calmeas, self)
        self.synchDialog.exec_()

        if prevSet!=self._calmeas.workingParamSet:
            self.DatasetChanged.emit()

    def _onInitButton(self):
        try:
            oldPeriods = list( self._calmeas.rasterPeriods )
            newPeriods = self._calmeas.requestTargetRasterPeriods()
            targetSymbols = self._calmeas.requestTargetSymbols()
            
        except Exception, e:
            self.InitializationFailed.emit()

            msg = QtGui.QMessageBox()
            msg.setIcon(QtGui.QMessageBox.Warning)
            msg.setText("Initialization exception")
            text = "Tried to initialize target:\n\n {0}".format(str(e))
            msg.setInformativeText(text)
            msg.setWindowTitle("Exception")
            msg.setStandardButtons(QtGui.QMessageBox.Ok)
            retval = msg.exec_()

        else:
            # Create ui and create default period mapping
            self.periodDialog = Period_diag(self, oldPeriods, newPeriods)

            if len(oldPeriods)>0 and len(set(oldPeriods).difference(set(newPeriods)))>0:
                # If already used periods does not exist anymore, make the user assign new periods
                self.periodDialog.exec_()
            
            for name,s in self._calmeas.workingSymbols.iteritems():
                if name in targetSymbols.keys():
                    # Apply mapping (old periods -> available periods)
                    targetSymbols[name].setPeriod( self.periodDialog.PeriodMapping[s.period_s] )
                    # Inherit isParameter
                    targetSymbols[name].isParameter = s.isParameter

            self._calmeas.workingSymbols = copy.deepcopy(targetSymbols)

            self._onSynchButton()

            self.InitializationSuccessful.emit()

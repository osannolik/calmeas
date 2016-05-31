#!/bin/env python

import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')
import sys
#from PyQt4 import QtCore, QtGui
import numpy as np
import json

#sys.path.insert(0, '../cobsser/')
from cobsser import CobsSer
from cobsser import DEFAULT_BAUDRATE

from comhandler import ComHandlerThread
from calmeas import CalMeas

from pyqtgraph.Qt import QtCore, QtGui 

import pyqtgraph as pg
pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')

cobsser = CobsSer()
comhandler = ComHandlerThread()
calmeas = CalMeas(comhandler)


class LongValidator(QtGui.QValidator):
    def __init__(self, minval=0, maxval=0, parent=None):
        super(LongValidator, self).__init__(parent)

        self._top = long(maxval)
        self._bottom = long(minval)

    def validate(self, s, pos):
        if str(s)=='':
            return (QtGui.QValidator.Intermediate, pos)

        try:
            toLong = long(s)
        except Exception, e:
            return (QtGui.QValidator.Invalid, pos)

        if self._bottom <= toLong <= self._top:
            return (QtGui.QValidator.Acceptable, pos)
        else:
            return (QtGui.QValidator.Invalid, pos)

    def setTop(self, maxval):
        self._top = long(maxval)

    def setBottom(self, minval):
        self._bottom = long(minval)

    def setRange(self, minval, maxval):
        self.setTop(maxval)
        self.setBottom(minval)

    def bottom(self):
        return self._bottom

    def top(self):
        return self._top


def getValidator(datatype):
    if datatype.isInteger():
        minval = np.iinfo(datatype.np_basetype).min
        maxval = np.iinfo(datatype.np_basetype).max

        if datatype.size() == 4 and not datatype.isSigned():
            return LongValidator(minval, maxval) # uint32
        else:
            return QtGui.QIntValidator(minval, maxval) # (u)int16 and int32
    else:
        minval = np.finfo(datatype.np_basetype).min
        maxval = np.finfo(datatype.np_basetype).max
        return QtGui.QDoubleValidator(minval, maxval, 10)

class SerialSettingsWidget(QtGui.QTabWidget):

    def __init__(self, parent=None):
        super(SerialSettingsWidget, self).__init__(parent)
        self.initGui()
        self.refreshAvailablePorts()
        
    def refreshAvailablePorts(self):
        avail_ports = cobsser.available_ports()
        self.portCombo.clear()
        self.portCombo.addItems(avail_ports)

    def serialConnect(self, connect, port = [], baud = DEFAULT_BAUDRATE):
        if baud=='':
            raise Exception("Please enter baud.")

        if connect and not cobsser.isConnected:
            try:
                comhandler.ResetParser()
                cobsser.connect(port, baud)
                cobsser.start_receive()
                cobsser.start_transmitt()
            except Exception, e:
                raise e
        elif not connect and cobsser.isConnected:
            try:
                cobsser.disconnect()
            except Exception, e:
                raise e

    def onConnectButton(self):
        try:
            self.serialConnect(not cobsser.isConnected, 
                               str(self.portCombo.currentText()), 
                               str(self.baudText.text()))
        except Exception, e:
            msg = QtGui.QMessageBox()
            msg.setIcon(QtGui.QMessageBox.Warning)
            msg.setText("Connection exception")
            text = "Tried to connect to port {0} at baud {1}:\n\n {2}".format(
                    self.portCombo.currentText(), self.baudText.text(), str(e))
            msg.setInformativeText(text)
            msg.setWindowTitle("Exception")
            msg.setStandardButtons(QtGui.QMessageBox.Ok)
            retval = msg.exec_()

        if cobsser.isConnected:
            self.connectBtn.setText('Disconnect')
            self.baudText.setEnabled(False)
        else:
            self.connectBtn.setText('Connect')
            self.baudText.setEnabled(True)

    def initGui(self):
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
        self.refreshBtn.clicked.connect(self.refreshAvailablePorts)
        self.refreshBtn.setFixedWidth(105)

        self.connectBtn = QtGui.QPushButton('Connect', self)
        self.connectBtn.clicked.connect(self.onConnectButton)
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

class ControllerWidget(QtGui.QWidget, QtCore.QObject):

    initSuccessful = QtCore.pyqtSignal(list)
    measurementStarted = QtCore.pyqtSignal()
    measurementStopped = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super(ControllerWidget, self).__init__(parent)

        self.initGui()

    def initGui(self):
        self.hbox = QtGui.QHBoxLayout()
        self.hbox.addStretch()
        self.vbox = QtGui.QVBoxLayout()

        self.InitBtn = QtGui.QPushButton('Initialize', self)
        self.InitBtn.clicked.connect(self.onInitButton)
        self.InitBtn.setFixedWidth(105)

        self.StartStopBtn = QtGui.QPushButton('Start', self)
        self.StartStopBtn.clicked.connect(self.onStartStopButton)
        self.StartStopBtn.setFixedWidth(105)
        self.StartStopBtn.setEnabled(False)

        self.vbox.addWidget(self.InitBtn)
        self.vbox.addWidget(self.StartStopBtn)

        self.hbox.addLayout(self.vbox)

        self.setLayout(self.hbox)

    def onInitButton(self):
        try:
            calmeas.initializeMeasurements()

        except Exception, e:
            self.StartStopBtn.setText('Start')
            self.StartStopBtn.setEnabled(False)

            msg = QtGui.QMessageBox()
            msg.setIcon(QtGui.QMessageBox.Warning)
            msg.setText("Initialization exception")
            text = "Tried to initialize target:\n\n {0}".format(str(e))
            msg.setInformativeText(text)
            msg.setWindowTitle("Exception")
            msg.setStandardButtons(QtGui.QMessageBox.Ok)
            retval = msg.exec_()

        else:
            self.StartStopBtn.setText('Start')
            self.StartStopBtn.setEnabled(True)

            self.initSuccessful.emit(calmeas.workingSymbols.values())

    def onStartStopButton(self):
        if 'Start'==self.StartStopBtn.text():
            calmeas.startMeasurements()
            self.StartStopBtn.setText('Stop')
            self.measurementStarted.emit()
        else:
            calmeas.stopMeasurements()
            self.StartStopBtn.setText('Start')
            self.measurementStopped.emit()

class SymbolListWidget(QtGui.QTabWidget):

    def __init__(self, parent=None):
        super(SymbolListWidget, self).__init__(parent)

        self.tab_meas = QtGui.QWidget()
        self.tab_param = QtGui.QWidget()

        self.addTab(self.tab_meas, "Symbols")
        self.addTab(self.tab_param, "Parameter Sets")

        layout_meas = QtGui.QVBoxLayout()
        layout_param = QtGui.QVBoxLayout()

        self.measWidget = MeasurementsWidget(self)
        layout_meas.addWidget(self.measWidget)

        self.paramWidget = ParametersWidget(self)
        layout_param.addWidget(self.paramWidget)

        self.tab_meas.setLayout(layout_meas)
        self.tab_param.setLayout(layout_param)

        self.measWidget.paramSetUpdated.connect(self.paramWidget.updateSymTree)
        self.measWidget.paramAdd.connect(self.paramWidget.addParam)
        self.paramWidget.paramSetSetted.connect(self.measWidget.updateCalTables)


    def addSymbols(self, symbols):
        self.measWidget.addMeasureSymbols(symbols)

    def updateWorkingSymbols(self, symbols):
        self.measWidget.treeWidget.clear()
        self.addSymbols(symbols)

class ParametersWidget(QtGui.QWidget):

    paramSetSetted = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        super(ParametersWidget, self).__init__(parent)

        self.parent = parent
        self.initGui()
        
    def initGui(self):
        layout = QtGui.QVBoxLayout(self)

        self.splitter = QtGui.QSplitter(QtCore.Qt.Vertical)

        self.dataSetList = QtGui.QListWidget(self)
        self.dataSetList.itemClicked.connect(self.selectedSetChanged)
        self.dataSetList.itemPressed.connect(self.selectedSetChanged)
        self.dataSetList.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.dataSetList.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.dataSetList.customContextMenuRequested.connect(self.openSetMenu)
        
        self.symTree = QtGui.QTreeWidget(self)
        #self.symTree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        #self.symTree.customContextMenuRequested.connect(self.openMenu)

        HEADERS = ( "Symbol", "Value" )
        self.symTree.setColumnCount( len(HEADERS) )
        self.symTree.setHeaderLabels( HEADERS )
        self.symTree.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)

        self.splitter.addWidget(self.dataSetList)
        self.splitter.addWidget(self.symTree)
        self.splitter.setCollapsible(0,False)
        self.splitter.setCollapsible(1,False)

        layout.addWidget(self.splitter)

        self.setLayout(layout)

        self.setIcon = QtGui.QIcon('icons/dset_icon.png')
        self.usedSetIcon = QtGui.QIcon('icons/dset_used_icon.png')

        self.impExpDialog = QtGui.QFileDialog()
        self.impExpDialog.setFilter(self.impExpDialog.filter() | QtCore.QDir.Hidden)
        self.impExpDialog.setDefaultSuffix('json')
        self.impExpDialog.setNameFilters(['JSON (*.json)'])

    def openSetMenu(self, position):
        selItems = self.dataSetList.selectedItems()

        menu = QtGui.QMenu()     
            
        if len(selItems)==1:        
            sa = menu.addAction("Apply")
            sa.triggered.connect(self.applyDataSet)
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

    def applyDataSet(self):
        selItem = self.dataSetList.currentItem()
        useSet = selItem.text()
        if useSet:
            calmeas.useParamSet(useSet)
            for i in range(self.dataSetList.count()):
                uncheck_item = self.dataSetList.item(i)
                uncheck_item.setIcon(self.setIcon)

            selItem.setIcon(self.usedSetIcon)
            self.updateCalTables(useSet)

    def updateCalTables(self, paramSet):
        updateVals = list()
        for sym, val in calmeas.getParamSet(paramSet).iteritems():
            symbol = calmeas.workingSymbols[sym]
            updateVals.append((sym, symbol.getValueStr(val)))

        self.paramSetSetted.emit(updateVals)

    def delDataSet(self):
        for selItem in self.dataSetList.selectedItems():
            try:
                calmeas.deleteParamSet(str(selItem.text()))
            except:
                pass
            else:
                self.dataSetList.takeItem(self.dataSetList.row(selItem))

    def impDataSet(self):
        self.impExpDialog.setAcceptMode(QtGui.QFileDialog.AcceptOpen)

        if self.impExpDialog.exec_() == QtGui.QDialog.Accepted:
            fname = str(self.impExpDialog.selectedFiles()[0])
            
            with open(fname) as f:
                data = json.load(f)

                for setName, setData in data.iteritems():
                    calmeas.importParamSet(setName, setData)
                    self.dataSetList.addItem(setName)
                    newItem = self.dataSetList.item(self.dataSetList.count() - 1)
                    newItem.setIcon(self.setIcon)

    def expDataSet(self):
        selItems = self.dataSetList.selectedItems()

        seldSets = dict()
        for itm in selItems:
            setName = str(itm.text())
            seldSets[setName] = calmeas.paramSet[setName]

        self.impExpDialog.setAcceptMode(QtGui.QFileDialog.AcceptSave)

        if self.impExpDialog.exec_() == QtGui.QDialog.Accepted:
            fname = str(self.impExpDialog.selectedFiles()[0])
            with open(fname, 'w') as f:
                json.dump(seldSets, f, indent=4, sort_keys=True)

    def newDataSet(self):
        selectedSet = self.dataSetList.currentItem()
        if selectedSet is None:
            selectedSet = ''
        else:
            selectedSet = str(selectedSet.text())

        newSetName = ''
        while not newSetName:
            newSetName, OK = QtGui.QInputDialog.getText(self, 'New Data Set', 'Please provide a name:', text=selectedSet)

        if OK:
            calmeas.newParamSet(str(newSetName), fromSet = selectedSet)
            self.dataSetList.addItem(newSetName)
            newItem = self.dataSetList.item(self.dataSetList.count() - 1)
            newItem.setIcon(self.setIcon)
            return newItem

        else:
            return None

    def selectedSetChanged(self, item):
        self.updateSymTree()

    def updateSymTree(self, pset=''):
        if pset=='':
            selItem = self.dataSetList.currentItem()
            if selItem is not None:
                pset = str(selItem.text())

        self.symTree.clear()

        if pset!='':
            for sym, val in calmeas.getParamSet(pset).iteritems():
                item = symTreeItem(self.symTree, calmeas.workingSymbols[sym], val)

            for column in range( self.symTree.columnCount() ):
                self.symTree.resizeColumnToContents( column )

    def addParam(self, symbols):
        # Will always be added to the working/target set
        if calmeas.workingParamSet=='':
            newItem = self.newDataSet()
            if newItem is not None:
                newItem.setIcon(self.usedSetIcon)
                self.dataSetList.setCurrentItem(newItem)
                newSetName = newItem.text()
                calmeas.useParamSet(newSetName)

        for s in symbols:
            calmeas.addParam(s.name)

class symTreeItem( QtGui.QTreeWidgetItem ):

    def __init__( self, parent, symbol, val):

        super( symTreeItem, self ).__init__( parent )

        self.setText( 0, symbol.name )

        self.setText( 1, symbol.getValueStr(val) )

class MeasurementsWidget(QtGui.QWidget):
    
    paramAdd = QtCore.pyqtSignal(list)
    paramSetUpdated = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super(MeasurementsWidget, self).__init__(parent)

        self.initGui()

        self.value_timer = QtCore.QTimer()
        self.value_timer.timeout.connect(self.updateValues)

        self._visualWidgets = list()
        self._calWidgets = list()

    def initGui(self):

        layout = QtGui.QVBoxLayout(self)
        
        self.treeWidget = QtGui.QTreeWidget(self)
        self.treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.treeWidget.customContextMenuRequested.connect(self.openMenu)

        HEADERS = ("Symbol", "Value", "Type", "Period [s]", "Description")
        self.treeWidget.setColumnCount( len(HEADERS) )
        self.treeWidget.setHeaderLabels( HEADERS )
        self.treeWidget.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)

        layout.addWidget(self.treeWidget)

        layout.addSpacing(0)

        self.setLayout(layout)

    def updateValues(self):
        iterator = QtGui.QTreeWidgetItemIterator(self.treeWidget)
        while iterator.value():
            item = iterator.value()
            item.updateValue()
            iterator += 1

    def startValueUpdater(self):
        iterator = QtGui.QTreeWidgetItemIterator(self.treeWidget)
        while iterator.value():
            item = iterator.value()
            item.periodCombo.setEnabled(False)
            iterator += 1

        self.value_timer.start(50)
        for visual in self._visualWidgets:
            visual.startUpdater()

    def stopValueUpdater(self):
        iterator = QtGui.QTreeWidgetItemIterator(self.treeWidget)
        while iterator.value():
            item = iterator.value()
            item.periodCombo.setEnabled(True)
            iterator += 1

        self.value_timer.stop()
        for visual in self._visualWidgets:
            visual.stopUpdater()

    def addMeasureSymbols(self, symbols):
        for s in symbols:
            item = MeasTreeItem( self.treeWidget, s)
            for column in range( self.treeWidget.columnCount() ):
                self.treeWidget.resizeColumnToContents( column )

            self.treeWidget.header().resizeSection(1, 120)

        return item

    def openMenu(self, position):
        selItems = self.treeWidget.selectedItems()
        if selItems:
            self.menu = QtGui.QMenu()
            self.createPeriodMenu()
            self.createAddToMenu()
            a = self.menu.exec_(self.treeWidget.viewport().mapToGlobal(position))

    def createPeriodMenu(self):
        self.submenuPeriod = QtGui.QMenu("Period")
        #sa = self.submenuPeriod.addAction("None")
        #sa.triggered.connect(lambda checked: self.moveToRaster(checked, None))
        #self.submenuPeriod.addSeparator()
        sa = self.submenuPeriod.addAction("Off")
        sa.triggered.connect(lambda checked, p="Off": self.moveToPeriod(checked, p))

        for p in calmeas.rasterPeriods:
            sa = self.submenuPeriod.addAction("{0} ms".format(p))
            sa.triggered.connect(lambda checked, p=p: self.moveToPeriod(checked, p))

        self.menu.addMenu(self.submenuPeriod)

    def createAddToMenu(self):
        self.submenu_add = QtGui.QMenu("Add to")

        sa = self.submenu_add.addAction("New YT-plotter")
        sa.triggered.connect(self.createNewYTplotter)
        sa = self.submenu_add.addAction("New Calibration Table")
        sa.triggered.connect(self.createNewCalTable)

        for cal in self._calWidgets:
            sa = self.submenu_add.addAction( cal.name )
            sa.triggered.connect(lambda checked, ct=cal: self.addSelectedToCalTable(ct))

        for visual in self._visualWidgets:
            sa = self.submenu_add.addAction( visual.name )
            sa.triggered.connect(lambda checked, yt=visual: self.addSelectedToYTplotter(yt))

        self.menu.addMenu(self.submenu_add)

    def addSelectedToYTplotter(self, yt):
        for item in self.treeWidget.selectedItems():
            s = calmeas.workingSymbols[item.symbolName]
            yt.addSymbol(s)

    def addSelectedToCalTable(self, ct):
        for item in self.treeWidget.selectedItems():
            s = calmeas.workingSymbols[item.symbolName]
            if ct.addSymbol(s):
                self.paramAdd.emit([s])

        self.paramSetUpdated.emit()

    def createNewYTplotter(self):
        yt = YT_plotter(self, name=str(len(self._visualWidgets)))
        yt.finished.connect(lambda result, yt=yt: self._visualWidgets.remove(yt))
        self.addSelectedToYTplotter(yt)

        if yt.plotItems()>0:
            self._visualWidgets.append(yt)
            yt.show()

            if calmeas.isStarted:
                yt.startUpdater()

    def createNewCalTable(self):
        ct = CalibrationTable(self, name=str(len(self._calWidgets)))
        ct.finished.connect(lambda result, ct=ct: self._calWidgets.remove(ct))
        self.addSelectedToCalTable(ct)

        if ct.calItems()>0:
            self._calWidgets.append(ct)
            ct.show()

    def updateCalTables(self, newVals):
        for ct in self._calWidgets:
            ct.updateValues(newVals)

    def moveToPeriod(self, checked, period):
        for item in self.treeWidget.selectedItems():
            indexToPeriod = item.periodCombo.findText(str(period))
            item.periodCombo.setCurrentIndex(indexToPeriod)

class YT_plotter(QtGui.QDialog):
    
    def __init__(self, parent=None, name=''):
        super(YT_plotter, self).__init__(parent)
        self.name = 'YT Plotter [{}]'.format(name)
        self.setWindowTitle(self.name)

        self.splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.layout = QtGui.QVBoxLayout()
        self.layout.setMargin(0)

        self.view = pg.GraphicsLayoutWidget() 
        self.splitter.addWidget(self.view)

        self.lgnd = QtGui.QTreeWidget(self)
        self.lgnd.setRootIsDecorated(False)
        self.lgnd.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.lgnd.customContextMenuRequested.connect(self.openMenu)
        self.lgnd.itemDoubleClicked.connect(self.clickedColor)
        self.lgnd.itemClicked.connect(self.clickedItem)
        self.lgnd.itemSelectionChanged.connect(self.changedSelection)
        lgndHdr = ("", "Symbol")
        self.lgnd.setColumnCount( len(lgndHdr) )
        self.lgnd.setHeaderLabels( lgndHdr )
        self.lgnd.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.lgnd.header().resizeSection(0, 20)
        self.lgnd.header().setResizeMode(0, QtGui.QHeaderView.Fixed)

        self.splitter.addWidget(self.lgnd)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self.layout.addWidget(self.splitter)
        self.setLayout(self.layout)

        self.mainplot = self.view.addPlot()
        self.mainplot.showGrid(x=True, y=True)

        self.mainplot.setMouseEnabled(x=False, y=True)

        self.menu = QtGui.QMenu()

        self._colors = [QtGui.QColor(0, 114, 189), 
                        QtGui.QColor(217, 83, 25), 
                        QtGui.QColor(237, 177, 32), 
                        QtGui.QColor(126, 47, 142), 
                        QtGui.QColor(119, 172, 48), 
                        QtGui.QColor(77, 190, 238), 
                        QtGui.QColor(162, 20, 47)]
        self._colorCntr = 0
        self._stacking = 0

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)

        self._displayRange = 2

        self._plotItems = list()

    def plotItems(self):
        return len(self._plotItems)

    def startUpdater(self, interval=20):
        for item in self._plotItems:
            symbolName = str(item.text(1))
            if symbolName in calmeas.workingSymbols.keys():
                symbol = calmeas.workingSymbols[symbolName]
                if symbol.period_s>0.0:
                    item.dataref = symbol.data
                    item.timeref = symbol.time
                    item.enable()
                else:
                    item.disable()

            else:
                # Remove symbol or disable curve
                item.disable()

        self.mainplot.setXRange(0, self._displayRange, padding=0)

        self.timer.start(interval)

    def stopUpdater(self):
        self.timer.stop()

    def nextColor(self):
        c = self._colors[self._colorCntr]
        self._colorCntr = (self._colorCntr+1) % len(self._colors)
        return c

    def clickedColor(self, item, col):
        if col==0:
            color = QtGui.QColorDialog.getColor()
            item.setColor(color)
            self.activateWindow()
            self.raise_()

    def clickedItem(self, item, col):
        self._stacking += 1
        item.plotData.setZValue(self._stacking)

        # item.setColor(item.color, width=2)

        # for notClickedItem in self._plotItems:
        #     if notClickedItem!=item:
        #         notClickedItem.setColor(notClickedItem.color, width=1)

    def changedSelection(self):
        pass
        # if self.lgnd.selectedItems():
        #     return

        # for notClickedItem in self._plotItems:
        #     notClickedItem.setColor(notClickedItem.color, width=1)


    def openMenu(self, position):
        items = self.lgnd.selectedItems()

        self.menu = QtGui.QMenu()
        action = self.menu.addAction("Remove")
        action.triggered.connect(lambda checked, items=items: self.removeSymbol(items))

        self.submenu_show_as = QtGui.QMenu("Show as")
        self.menu.addMenu(self.submenu_show_as)
        action = self.submenu_show_as.addAction( "Lines" )
        action.triggered.connect(lambda checked, items=items: self.setStepMode(items, False))
        action = self.submenu_show_as.addAction( "Steps" )
        action.triggered.connect(lambda checked, items=items: self.setStepMode(items, True))

        if items:
            #self.submenu_move = QtGui.QMenu("Move to")
            #self.submenu_move.addAction("")
            #self.menu.addMenu(self.submenu_move)
            a = self.menu.exec_(self.lgnd.viewport().mapToGlobal(position))

    def setStepMode(self, items, onoff):
        root = self.lgnd.invisibleRootItem()
        for item in items:
            item.setStepMode(onoff)

        self.update_plot()

    def removeSymbol(self, items):
        root = self.lgnd.invisibleRootItem()
        for item in items:
            item.disable()
            self._plotItems.remove(item)
            self.mainplot.removeItem(item)
            root.removeChild(item)

    def addSymbol(self, symbol):
        if symbol.name not in [str(item.text(1)) for item in self._plotItems]:# and symbol.period_s>0.0:
            plotItem = YT_plotter_item(self, symbol)
            self._plotItems.append( plotItem )
            if calmeas.isStarted:
                plotItem.enable()

    def update_plot(self):
        tmax = None
        for item in self._plotItems:
            curve_range = item.updateCurve()
            if curve_range is not None:
                tmax = max(tmax, curve_range[1])

        if tmax>=self._displayRange:
            self.mainplot.setXRange(tmax-self._displayRange, tmax, padding=0)

    def closeEvent(self, event):
        self.timer.stop()
        self.finished.emit(0)
        event.accept()

class YT_plotter_item( QtGui.QTreeWidgetItem ):

    def __init__( self, yt_plotter, symbol ):

        super( YT_plotter_item, self ).__init__( yt_plotter.lgnd )

        #self.setText( 0, "" )
        self.setText( 1, symbol.name )
        self.dataref = symbol.data
        self.timeref = symbol.time

        self.plotData = yt_plotter.mainplot.plot()
        #self.plotData.setData(y=self.dataref)
        self.setColor(yt_plotter.nextColor())

        self._enabled = False
        self._useStepMode = False

    def setStepMode(self, onoff):
        self._useStepMode = onoff

    def setColor(self, color):
        self.color = color
        self.setBackgroundColor(0, color)
        self.plotData.setPen(pg.mkPen(color=color, width=1, style=QtCore.Qt.SolidLine))

    def enable(self):
        self.plotData.setPen(pg.mkPen(color=self.color, width=1, style=QtCore.Qt.SolidLine))
        self._enabled = True

    def disable(self):
        self.plotData.setPen(pg.mkPen(None))
        self._enabled = False

    def updateCurve(self):
        if self._enabled:
            if self._useStepMode:
                self.plotData.setData(y=self.dataref[1:], x=self.timeref, stepMode=self._useStepMode)
            else:
                self.plotData.setData(y=self.dataref, x=self.timeref, stepMode=self._useStepMode)
            return (min(self.timeref), max(self.timeref))
        else:
            self.disable()
            return None


class CalibrationTable(QtGui.QDialog):
    
    def __init__(self, parent=None, name=''):
        super(CalibrationTable, self).__init__(parent)

        self.paramSetUpdated = parent.paramSetUpdated

        self.name = 'Calibration Table [{}]'.format(name)
        self.setWindowTitle(self.name)

        self.layout = QtGui.QVBoxLayout()
        self.layout.setMargin(0)

        self.tree = QtGui.QTreeWidget(self)
        #self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.openMenu)
        self.tree.itemSelectionChanged.connect(self.changedSelection)
        treeHdr = ( "Symbol", "Value", "Type", "Description")
        self.tree.setColumnCount( len(treeHdr) )
        self.tree.setHeaderLabels( treeHdr )

        self.layout.addWidget(self.tree)

        self.setLayout(self.layout)

        self.resize(600, 300)

        self._calItems = list()

    def calItems(self):
        return len(self._calItems)

    def openMenu(self, position):
        items = self.tree.selectedItems()

        self.menu = QtGui.QMenu()
        action = self.menu.addAction("Remove")
        action.triggered.connect(lambda checked, items=items: self.removeSymbol(items))

        if items:
            #self.submenu_move = QtGui.QMenu("Move to")
            #self.submenu_move.addAction("")
            #self.menu.addMenu(self.submenu_move)
            a = self.menu.exec_(self.tree.viewport().mapToGlobal(position))

    def changedSelection(self):
        pass

    def removeSymbol(self, items):
        root = self.tree.invisibleRootItem()
        for item in items:
            self._calItems.remove(item)
            root.removeChild(item)

    def addSymbol(self, symbol):
        if symbol.name not in [str(item.text(0)) for item in self._calItems]:
            try:
                calItem = CalTable_item(self, symbol)
            except Exception, e:
                pass
            else:
                self._calItems.append( calItem )
                for column in range( self.tree.columnCount() ):
                    self.tree.resizeColumnToContents( column )

                return True

        return False

    def updateValues(self, newVals):
        symNames, values = zip(*newVals)
        for calItem in self._calItems:
            try:
                idx = symNames.index(str(calItem.text(0)))
            except:
                pass
            else:
                calItem.setValue( values[idx] )

class CalTable_item( QtGui.QTreeWidgetItem ):

    def __init__( self, calTable, symbol ):

        super( CalTable_item, self ).__init__( calTable.tree )

        self.paramSetUpdated = calTable.paramSetUpdated

        self.setText( 0, symbol.name )

        if symbol.datatype.isEnum():
            self.valueEdit = QtGui.QComboBox()
            self.valueEdit.currentIndexChanged.connect(self.updatedValue)
            itemsStr = ["({0}) {1}".format(n,d) for n,d in symbol.datatype.enumerations.iteritems()]
            self.valueEdit.addItems(itemsStr)
            self.treeWidget().setItemWidget( self, 1, self.valueEdit )
        else:
            #self.setText( 1, symbol.getValueStr() )
            self.valueEdit = QtGui.QLineEdit()
            self.valueEdit.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.valueEdit.setValidator(getValidator(symbol.datatype))
            self.valueEdit.textEdited.connect(self.editedValue)
            self.valueEdit.editingFinished.connect(self.updatedValue)
            self.treeWidget().setItemWidget( self, 1, self.valueEdit )

        self.setTextAlignment( 1, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.setText( 2, symbol.datatype.text )
        self.setText( 3, symbol.desc )

        self._prevValue = ''
        self._isEdited = True

    def editedValue(self, string):
        self._isEdited = (string != self._prevValue)
        self._prevValue = string

    def updatedValue(self):
        if self._isEdited:
            val = str(self.valueEdit.text())
            calmeas.tuneTargetParameter(str(self.text(0)), val.replace(',','.'))
            self.paramSetUpdated.emit()
            self._isEdited = False

    def setValue(self, value):
        self.valueEdit.setText( str(value) )


class MeasTreeItem( QtGui.QTreeWidgetItem ):

    def __init__( self, parent, symbol):

        super( MeasTreeItem, self ).__init__( parent )

        self.symbolName = symbol.name

        self.setText( 0, symbol.name )
        self.setText( 1, symbol.getValueStr() )
        self.setTextAlignment( 1, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.setText( 2, symbol.datatype.text )

        self.periodCombo = QtGui.QComboBox()
        self.periodCombo.addItem("Off")
        self.periodCombo.addItems(map(str, calmeas.rasterPeriods))
        self.treeWidget().setItemWidget( self, 3, self.periodCombo )

        indexToPeriod = self.periodCombo.findText(str(symbol.period_s))
        if indexToPeriod>=0:
            self.periodCombo.setCurrentIndex(indexToPeriod)
        else:
            self.periodCombo.setCurrentIndex(0)

        self.setText( 4, symbol.desc )

        self.periodCombo.currentIndexChanged.connect(self.updatedPeriod)

        self.prevVal = 0

    def updatedPeriod(self, index):
        perStr = str(self.periodCombo.itemText(index))
        try:
            per = float(perStr)
        except:
            calmeas.workingSymbols[self.symbolName].setPeriod( 0.0 )
        else:
            calmeas.workingSymbols[self.symbolName].setPeriod( per )

    def updateValue(self):
        sym = calmeas.workingSymbols[self.symbolName]
        self.setText( 1, sym.getValueStr() )


class CalMeas_UI(QtGui.QMainWindow):

    def __init__(self, parent=None):

        super(CalMeas_UI, self).__init__(parent)

        self.mainWidget = QtGui.QWidget(self) # dummy widget to contain the layout manager
        self.setCentralWidget(self.mainWidget)

        self.topWidget = QtGui.QWidget(self)
        self.appWidget = QtGui.QWidget(self)

        self.mainLayout = QtGui.QVBoxLayout(self.mainWidget)
        self.topLayout = QtGui.QHBoxLayout(self.topWidget)
        self.appLayout = QtGui.QHBoxLayout(self.appWidget)

        self.mainLayout.addWidget(self.topWidget, stretch=0)
        self.mainLayout.addWidget(self.appWidget, stretch=1)

        self.serialSettingsWidget = SerialSettingsWidget()
        self.controlWidget = ControllerWidget()

        self.topLayout.addWidget(self.serialSettingsWidget, stretch=0)
        self.topLayout.addStretch()
        self.topLayout.addWidget(self.controlWidget, stretch=0)

        self.symbolWidget = SymbolListWidget()

        self.appLayout.addWidget(self.symbolWidget, stretch=1)

        self.resize(800, 600)
        
        self.controlWidget.initSuccessful.connect(self.symbolWidget.updateWorkingSymbols)
        self.controlWidget.measurementStarted.connect(self.symbolWidget.measWidget.startValueUpdater)
        self.controlWidget.measurementStopped.connect(self.symbolWidget.measWidget.stopValueUpdater)



def open_app():


    app = QtGui.QApplication(sys.argv)

    QtCore.QLocale.setDefault( QtCore.QLocale('en_US') )

    app.aboutToQuit.connect(on_exit)

    comhandler.setByteQueue_Rx(cobsser.Rx_fifo)
    comhandler.setByteQueue_Tx(cobsser.Tx_fifo)
    comhandler.start()

    cmui = CalMeas_UI()
    cmui.show()

    sys.exit(app.exec_())

def on_exit():
    if cobsser.isConnected:
        try:
            cobsser.disconnect()
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
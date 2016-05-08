#!/bin/env python

import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')
import sys
#from PyQt4 import QtCore, QtGui
import numpy as np

#sys.path.insert(0, '../cobsser/')
from cobsser import CobsSer
from cobsser import DEFAULT_BAUDRATE

from comhandler import ComHandlerThread
from calmeas import CalMeas

from pyqtgraph.Qt import QtCore, QtGui 

import pyqtgraph as pg
pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')

from time import time

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
        self.addTab(self.tab_param, "Parameters")

        layout_meas = QtGui.QVBoxLayout()
        layout_param = QtGui.QVBoxLayout()

        self.paramWidget = ParametersWidget(self)
        layout_param.addWidget(self.paramWidget)

        self.measWidget = MeasurementsWidget(self)
        layout_meas.addWidget(self.measWidget)

        self.tab_meas.setLayout(layout_meas)
        self.tab_param.setLayout(layout_param)

    def addSymbols(self, symbols):
        self.measWidget.addMeasureSymbols(symbols)

    def updateWorkingSymbols(self, symbols):
        self.measWidget.treeWidget.clear()
        self.addSymbols(symbols)


class ParametersWidget(QtGui.QWidget):

    def __init__(self, parent=None, name=''):
        super(ParametersWidget, self).__init__(parent)

        #self.name = 'Calibration Table [{}]'.format(name)
        self.name = "Parameters"
        self.parent = parent
        self.initGui()

    def initGui(self):
        
        self.layout = QtGui.QVBoxLayout()
        #self.layout.setMargin(0)

        self.tree = QtGui.QTreeWidget(self)
        #self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.openMenu)
        self.tree.itemSelectionChanged.connect(self.changedSelection)
        treeHdr = ( "Symbol", "Value", "Type", "Description")
        self.tree.setColumnCount( len(treeHdr) )
        self.tree.setHeaderLabels( treeHdr )



        self.dataSetCombo = QtGui.QComboBox(self)
        self.dataSetCombo.setMinimumWidth(150)

        self.newDataSetBtn = QtGui.QPushButton('New...', self)
        self.newDataSetBtn.clicked.connect(self.newDataSetForm)
        self.newDataSetBtn.setFixedWidth(120)

        groupBox = QtGui.QGroupBox("Data set")
        hlayout = QtGui.QHBoxLayout(groupBox)

        hlayout.addWidget(self.dataSetCombo)
        hlayout.addWidget(self.newDataSetBtn)
        self.layout.addWidget(groupBox)



        self.layout.addWidget(self.tree)

        self.setLayout(self.layout)

        self._calItems = list()

    def calItems(self):
        return len(self._calItems)

    def newDataSetForm(self):
        print 'Save data etc'

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
            root.removeChild(item)
            self._calItems.remove(item)

    def addSymbol(self, symbol):
        if symbol.name not in [str(item.text(0)) for item in self._calItems]:# and symbol.period_s>0.0:
            calItem = CalTable_item(self, symbol)
            self._calItems.append( calItem )


# class ParametersWidget(QtGui.QWidget):

#     def __init__(self, parent=None):
#         super(ParametersWidget, self).__init__(parent)

#         self.parent = parent
#         self.initGui()
        

#     def initGui(self):

#         layout = QtGui.QVBoxLayout(self)
        
#         self.treeWidget = QtGui.QTreeWidget(self)
#         self.treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
#         self.treeWidget.customContextMenuRequested.connect(self.openMenu)

#         HEADERS = ( "Symbol", "Value", "Type", "Description")
#         self.treeWidget.setColumnCount( len(HEADERS) )
#         self.treeWidget.setHeaderLabels( HEADERS )
#         self.treeWidget.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)


#             #item = self.addParamSymbol(s)


#         self.dataSetCombo = QtGui.QComboBox(self)
#         self.dataSetCombo.setMinimumWidth(150)

#         self.newDataSetBtn = QtGui.QPushButton('New...', self)
#         self.newDataSetBtn.clicked.connect(self.newDataSetForm)
#         self.newDataSetBtn.setFixedWidth(120)
#         layout.addWidget(self.newDataSetBtn)

#         ## Context menu
#         self.createContextMenu()

#         #self.menu.addSeparator()
#         groupBox = QtGui.QGroupBox("Data set")
#         hlayout = QtGui.QHBoxLayout(groupBox)

#         hlayout.addWidget(self.dataSetCombo)
#         hlayout.addWidget(self.newDataSetBtn)
#         layout.addWidget(groupBox)
#         layout.addWidget(self.treeWidget)

#         #layout.addSpacing(0)

#         applyBtn = QtGui.QPushButton('Apply', self)
#         applyBtn.clicked.connect(self.applyDataSet)
#         applyBtn.setFixedWidth(100)
#         layout.addWidget(applyBtn, alignment=QtCore.Qt.AlignRight)

#         self.setLayout(layout)

#     def applyDataSet(self):
#         print 'Update parameters on target!'
#         #comcmds.requestWrite(0x20000051, ctypes.c_uint32(0x11223344))



#     def newDataSetForm(self):
#         print 'Save data etc'

#     def addParamSymbol(self, s):
#         item = ParamTreeItem( self.treeWidget, s)
#         for column in range( self.treeWidget.columnCount() ):
#             self.treeWidget.resizeColumnToContents( column )
#         return item

#     def createContextMenu(self):
#         self.menu = QtGui.QMenu()

#     def openMenu(self, position):
#         self.createContextMenu()

#         items = self.treeWidget.selectedItems()

#         self.submenu_add = QtGui.QMenu("Add to")
#         self.submenu_add.addAction("")
#         self.menu.addMenu(self.submenu_add)

#         a = self.menu.exec_(self.treeWidget.viewport().mapToGlobal(position))


# class ParamTreeItem( QtGui.QTreeWidgetItem ):

#     def __init__( self, parent, symbol):

#         super( ParamTreeItem, self ).__init__( parent )

#         self.symbolName = symbol.name

#         self.setText( 0, symbol.name )

#         if symbol.dt.isEnum():
#             self.valueCombo = QtGui.QComboBox()
#             self.valueCombo.currentIndexChanged.connect(self.updatedValue)
#             itemsStr = ["({0}) {1}".format(n,d) for n,d in symbol.dt.enumerations.iteritems()]
#             self.valueCombo.addItems(itemsStr)
#             self.treeWidget().setItemWidget( self, 1, self.valueCombo )
#         else:
#             #self.setText( 1, symbol.getValueStr() )
#             self.valueEdit = QtGui.QLineEdit()
#             self.valueEdit.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
#             self.valueEdit.setValidator(symbol.dt.getValidator())
#             self.valueEdit.editingFinished.connect(self.updatedValue)
#             self.treeWidget().setItemWidget( self, 1, self.valueEdit )

        
#         self.setTextAlignment( 1, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
#         self.setText( 2, symbol.dt.text )
#         self.setText( 3, symbol.desc )

#     def updatedValue(self):
#         print 'new val!'


class MeasurementsWidget(QtGui.QWidget):
    
    def __init__(self, parent=None):
        super(MeasurementsWidget, self).__init__(parent)

        self.initGui()

        self.value_timer = QtCore.QTimer()
        self.value_timer.timeout.connect(self.updateValues)

        self._visualWidgets = list()
        self._calWidgets = [parent.paramWidget]
        
        self._updateTimes = list()
        self.tick = time()
        self.sameVal = 0

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

        # self._updateTimes.append( time() - self.tick )

        # if len(self._updateTimes)>=1000:
        #     f = open('out_values.txt','w')
        #     f.write(','.join(map(str, self._updateTimes)))
        #     f.close()
        #     print "printed update times"
        #     self._updateTimes = list()
        #     self.sameVal = 0

        # self.tick = time()
        

    def startValueUpdater(self):
        iterator = QtGui.QTreeWidgetItemIterator(self.treeWidget)
        while iterator.value():
            item = iterator.value()
            item.periodCombo.setEnabled(False)
            iterator += 1

        self.value_timer.start(50)
        for visual in self._visualWidgets:
            visual.startUpdater()

        self.tick = time()

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
        
        #sa = self.submenu_add.addAction("New Calibration Table")
        #sa.triggered.connect(self.createNewCalTable)

        for cal in self._calWidgets:
            sa = self.submenu_add.addAction( cal.name )
            sa.triggered.connect(lambda checked, ct=cal: self.addSelectedToCalTable(ct))

        sa = self.submenu_add.addAction("New YT-plotter")
        sa.triggered.connect(self.createNewYTplotter)

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
            ct.addSymbol(s)

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

        #self._plotTime = list()

        #self.tick = time()

        #w1 = self.view.addPlot(title="Plot 1")
        #w1.setLabel('left', "Y Axis", units='A')
        #w1.setLabel('bottom', "Time", units='s')

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

        #self.tick = time()

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

        #     self._plotTime.append( time() - self.tick )

        #     if len(self._plotTime)==1000:
        #         f = open('out.txt','w')
        #         f.write(','.join(map(str, self._plotTime)))
        #         f.close()
        #         print "printed plot times"
        #         self._plotTime = list()

        # self.tick = time()


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
            root.removeChild(item)

    def addSymbol(self, symbol):
        if symbol.name not in [str(item.text(1)) for item in self._calItems]:# and symbol.period_s>0.0:
            calItem = CalTable_item(self, symbol)
            self._calItems.append( calItem )

class CalTable_item( QtGui.QTreeWidgetItem ):

    def __init__( self, calTable, symbol ):

        super( CalTable_item, self ).__init__( calTable.tree )

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
            calmeas.tuneTargetParameter(str(self.text(0)), str(self.valueEdit.text()))
            self._isEdited = False


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

        # self.chBox = list()
        # for i in range(0,4):
        #     self.chBox.append(QtGui.QCheckBox())
        #     self.chBox[i].stateChanged.connect(lambda checked,i=i: self.rasterCheckBox_cb(i, self.chBox[i]))
        #     self.treeWidget().setItemWidget( self, 2+i, self.chBox[i] )

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


    # def rasterCheckBox_cb(self, i, chBox):
    #     #print checked
    #     if chBox.isChecked():
    #         for chb in range(0,4):
    #             if chb != i:
    #                 self.chBox[chb].setChecked(0)

            #print self.symbol.name + ' ' + str(i)
            #print self.data(0, QtCore.Qt.UserRole).toPyObject()
            #self.parent().chBox[i].setChecked(1)


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
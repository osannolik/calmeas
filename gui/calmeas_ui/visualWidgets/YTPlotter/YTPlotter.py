import logging
logging.basicConfig(level=logging.DEBUG, datefmt='%H:%M:%S', 
                    format='%(asctime)s,%(msecs)-3d %(levelname)-8s [%(threadName)s:%(filename)s:%(lineno)d] %(message)s')

import pyqtgraph as pg
pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')

from PyQt4 import QtCore, QtGui

from visualWidgets.VisualBase import VisualBase


class YTPlotter(VisualBase):

    IDENT = "YT-Plotter"

    LEGEND_HEADER = ("", "Symbol")
    MENU_REMOVE_TEXT = "Remove"

    COLORS = [QtGui.QColor(0, 114, 189), 
              QtGui.QColor(217, 83, 25), 
              QtGui.QColor(237, 177, 32), 
              QtGui.QColor(126, 47, 142), 
              QtGui.QColor(119, 172, 48), 
              QtGui.QColor(77, 190, 238), 
              QtGui.QColor(162, 20, 47)]

    def __init__(self, parent, calmeas):
        super(YTPlotter, self).__init__(parent, calmeas)

        splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        layout = QtGui.QVBoxLayout()
        layout.setMargin(0)

        self.view = pg.GraphicsLayoutWidget() 
        splitter.addWidget(self.view)

        self._lgnd = QtGui.QTreeWidget(self)
        self._lgnd.setRootIsDecorated(False)
        self._lgnd.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._lgnd.customContextMenuRequested.connect(self._openMenu)
        self._lgnd.itemDoubleClicked.connect(self._clickedColor)
        self._lgnd.itemClicked.connect(self._clickedItem)
        self._lgnd.setColumnCount( len(self.LEGEND_HEADER) )
        self._lgnd.setHeaderLabels( self.LEGEND_HEADER )
        self._lgnd.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self._lgnd.header().resizeSection(0, 20)
        self._lgnd.header().setResizeMode(0, QtGui.QHeaderView.Fixed)

        splitter.addWidget(self._lgnd)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        layout.addWidget(splitter)
        self.setLayout(layout)

        self.mainplot = self.view.addPlot()
        self.mainplot.showGrid(x=True, y=True)

        self.resize(750, 360)

        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.update)

        self.updateInterval = 20

        self._colorCntr = 0
        self._stacking = 0
        self._displayRange = 10
        self._time = dict()

    def addSymbols(self, symbolNames):
        for symbolName in symbolNames:
            if symbolName not in self.symbols():
                plotItem = YTPlotterItem(self, symbolName)
                if self._calmeas.isStarted:
                    self._setTimeVector(symbolName)
                    plotItem.enable()

    def removeSymbols(self, symbolNames):
        root = self._lgnd.invisibleRootItem()
        for item in self._items():
            if item.symbolName in symbolNames:
                item.disable()
                self.mainplot.removeItem(item)
                root.removeChild(item)

    def _setTimeVector(self, symbolName):
        try:
            p = self.getSymbolPeriod(symbolName)
        except Exception, e:
            pass
        else:
            if p>0.0:
                self._time[symbolName] = [-p*x for x in range(int(self._displayRange/p)-1,-1,-1)]
            else:
                self._time[symbolName] = [0]*len(super(YTPlotter, self).getSymbolTime(symbolName))

    def start(self):
        for item in self._items():
            self._setTimeVector(item.symbolName)
            item.enable()

        self._timer.start(self.updateInterval)

    def stop(self):
        self._timer.stop()

    def update(self):
        tmax = None
        for item in self._items():
            item.updateCurve()

    def symbols(self):
        return [item.symbolName for item in self._items()]

    def _items(self):
        items = list()
        iterator = QtGui.QTreeWidgetItemIterator(self._lgnd)
        while iterator.value():
            items.append(iterator.value())
            iterator += 1
        return items

    def nextColor(self):
        c = self.COLORS[self._colorCntr]
        self._colorCntr = (self._colorCntr+1) % len(self.COLORS)
        return c

    def _clickedColor(self, item, col):
        if col==0:
            color = QtGui.QColorDialog.getColor()
            item.setColor(color)
            self.activateWindow()
            self.raise_()

    def _clickedItem(self, item, col):
        self._stacking += 1
        item.plotData.setZValue(self._stacking)

    def _openMenu(self, position):
        items = self._lgnd.selectedItems()
        symbolNames = [item.symbolName for item in items]

        menu = QtGui.QMenu()
        action = menu.addAction(self.MENU_REMOVE_TEXT)
        action.triggered.connect(lambda checked, symbolNames=symbolNames: self.removeSymbols(symbolNames))

        submenu_show_as = QtGui.QMenu("Show as")
        menu.addMenu(submenu_show_as)
        action = submenu_show_as.addAction( "Lines" )
        action.triggered.connect(lambda checked, items=items: self.setStepMode(items, False))
        action = submenu_show_as.addAction( "Steps" )
        action.triggered.connect(lambda checked, items=items: self.setStepMode(items, True))

        if items:
            a = menu.exec_(self._lgnd.viewport().mapToGlobal(position))

    def setStepMode(self, items, onoff):
        root = self._lgnd.invisibleRootItem()
        for item in items:
            item.setStepMode(onoff)

        self.update()

    def getSymbolTime(self, symbolName):
        '''A helper for getting the time buffer of a symbol'''
        return self._time[symbolName]


class YTPlotterItem( QtGui.QTreeWidgetItem ):

    def __init__( self, YTPlotter, symbolName ):
        super(YTPlotterItem, self).__init__(YTPlotter._lgnd)

        self.symbolName = symbolName

        self._YTPlotter = YTPlotter

        self.setText( 1, symbolName )

        self.plotData = YTPlotter.mainplot.plot()

        self._enabled = False
        self._useStepMode = False

        self.setColor(YTPlotter.nextColor())

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
            try:
                data = self._YTPlotter.getSymbolData(self.symbolName)
                time = self._YTPlotter.getSymbolTime(self.symbolName)
            except Exception, e:
                # symbolName might not exist anymore
                pass
            else:
                if self._useStepMode:
                    self.plotData.setData(y=data[1:], x=time, stepMode=self._useStepMode)
                else:
                    self.plotData.setData(y=data, x=time, stepMode=self._useStepMode)


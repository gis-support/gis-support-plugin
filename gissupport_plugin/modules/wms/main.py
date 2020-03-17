# -*- coding: utf-8 -*-
from gissupport_plugin.modules.wms.baza_wms_dialog import BazaWMSDialog
from gissupport_plugin.modules.base import BaseModule
#from .resources import *
from qgis.PyQt.QtWidgets import QTableWidgetItem, QHeaderView
from qgis.PyQt.QtGui import QPixmap, QStandardItemModel, QStandardItem
from qgis.PyQt.QtCore import QSortFilterProxyModel, QItemSelectionModel, Qt
from qgis.core import QgsProject, QgsRasterLayer, Qgis
from qgis.utils import iface
from gissupport_plugin.modules.wms.models import ServicesTableModel, ServicesProxyModel
import json
from os import path
from owslib.wms import WebMapService
import requests.exceptions
import urllib


class Main(BaseModule):
    module_name = "Baza krajowych usług WMS"

    def __init__(self, parent):
        self.parent = parent
        
        self.canvas = iface.mapCanvas()
        self.dlg = BazaWMSDialog()
        self.curServiceData = None

        self.project = QgsProject.instance()
        #Load WMS services list from json file
        with open(path.join(path.dirname(__file__), 'services.json')) as servicesJson:
            self.services = json.load(servicesJson)

        #Models
        servicesProxyModel = ServicesProxyModel()
        servicesProxyModel.sort(0)
        servicesProxyModel.setSourceModel(ServicesTableModel())
        self.dlg.servicesTableView.setModel(servicesProxyModel)
        self.servicesTableModel = self.dlg.servicesTableView.model().sourceModel()
        self.dlg.servicesTableView.setSortingEnabled(False)

        #Initialize table headers
        self.dlg.servicesTableView.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.dlg.servicesTableView.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.dlg.servicesTableView.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.dlg.servicesTableView.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        self.dlg.servicesTableView.setColumnWidth(0, 20)
        self.dlg.servicesTableView.setColumnWidth(1, 100)
        self.dlg.servicesTableView.setColumnWidth(2, 300)

        self.dlg.layersTableWidget.setHorizontalHeaderLabels(['Nr', 'Nazwa', 'Tytuł', 'Streszczenie', 'Układ współrzędnych'])
        self.dlg.layersTableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.dlg.layersTableWidget.setColumnCount(5)
        self.dlg.layersTableWidget.setColumnWidth(0, 20)
        self.dlg.layersTableWidget.setColumnWidth(1, 70)
        self.dlg.layersTableWidget.setColumnWidth(2, 170)
        self.dlg.layersTableWidget.setColumnWidth(3, 170)
        self.dlg.layersTableWidget.setColumnWidth(4, 90)

        #Connect slots to signals
        self.dlg.servicesTableView.selectionModel().selectionChanged.connect(self.showDescription)
        self.dlg.searchLineEdit.textChanged.connect(servicesProxyModel.setFilterRegExp)
        self.dlg.getLayersButton.clicked.connect(self.loadLayers)
        self.dlg.layersTableWidget.itemSelectionChanged.connect(self.enableAddToMap)
        self.dlg.addLayersButton.clicked.connect(self.addToMap)

        self.updateServicesList()

        #Zarejestrowanie we wtyczce

        self.dlg.lblInfo.setPixmap(QPixmap(':/plugins/plugin/info.png'))
        self.dlg.lblInfo.setToolTip((
            "Brakuje adresu WMS, którego szukasz?\n"
            "Napisz do nas: info@gis-support.pl"))
        
        self.parent.add_action(
            ":/plugins/gissupport_plugin/wms/wms.png",
            self.module_name,
            callback = self.dlg.show,
            checkable = False,
            parent = iface.mainWindow(),
            add_to_topmenu=True 
        )
    
    def unload(self):
        """ Wyłączenie modułu """
        del self.dlg

    def updateServicesList(self):
        """ Fills the Table Widget with a list of WMS Services """
        self.servicesTableModel.insertRows(0, self.services)

    def showDescription(self):
        self.dlg.layersTableWidget.setRowCount(0)
        self.dlg.layersTableWidget.clearContents()
        row = self.dlg.servicesTableView.selectionModel().selectedRows()
        if len(row) > 0:
            selected = row[0]
            self.curServiceData = selected.sibling(selected.row(), selected.column()).data(role=Qt.UserRole)
            self.dlg.descriptionTextEdit.setPlainText(self.curServiceData['Opis'])

    def loadLayers(self):
        self.dlg.layersTableWidget.setRowCount(0)
        defaultCrs = 'EPSG:2180'
        if self.curServiceData:
            try:
                wmsCapabilities = WebMapService(self.curServiceData['url'])
            except AttributeError:
                wmsCapabilities = WebMapService(self.curServiceData['url'], version='1.3.0')
            except requests.exceptions.ReadTimeout:
                iface.messageBar().pushMessage(
                    'Baza krajowych usług WMS',
                    'Serwer WMS nie odpowiada. Spróbuj ponownie później.',
                    level=Qgis.Critical
                )
                return 1
            except requests.exceptions.SSLError:
                iface.messageBar().pushMessage(
                    'Baza krajowych usług WMS',
                    'Błąd połączenia z serwerem WMS.',
                    level=Qgis.Critical
                )
                return 1
            for nr, layer in enumerate(list(wmsCapabilities.contents)):
                wmsLayer = wmsCapabilities[layer]
                self.dlg.layersTableWidget.insertRow(nr)
                self.dlg.layersTableWidget.setItem(nr, 0, QTableWidgetItem(str(nr+1)))
                self.dlg.layersTableWidget.setItem(nr, 1, QTableWidgetItem(wmsLayer.name))
                self.dlg.layersTableWidget.setItem(nr, 2, QTableWidgetItem(wmsLayer.title))
                self.dlg.layersTableWidget.setItem(nr, 3, QTableWidgetItem(wmsLayer.abstract))
                self.dlg.layersTableWidget.setItem(nr, 4, QTableWidgetItem(defaultCrs if defaultCrs in wmsLayer.crsOptions else wmsLayer.crsOptions[0]))

    def enableAddToMap(self):
        layerSelected = True if self.dlg.layersTableWidget.selectionModel().selectedRows() else False
        self.dlg.addLayersButton.setEnabled(layerSelected)

    def addToMap(self):
        selectedRows = [i.row() for i in self.dlg.layersTableWidget.selectionModel().selectedRows()]
        for layerId in selectedRows:
            url = (
                "contextualWMSLegend=0&"
                "crs={}&"
                "dpiMode=7&"
                "featureCount=10&"
                "format=image/jpeg&"
                "layers={}&"
                "styles=&"
                "url={}".format(
                    self.dlg.layersTableWidget.item(layerId, 4).text(),
                    urllib.parse.quote(self.dlg.layersTableWidget.item(layerId, 1).text()),
                    self.curServiceData['url']
                )
            )
            wmsLayer = QgsRasterLayer(url, self.dlg.layersTableWidget.item(layerId, 2).text(), 'wms')
            if wmsLayer.isValid():
                QgsProject.instance().addMapLayer(wmsLayer)
            else:
                iface.messageBar().pushMessage(
                    'Baza krajowych usług WMS',
                    'Nie udało się wczytać warstwy %s' % self.dlg.layersTableWidget.item(layerId, 2).text(),
                    level=Qgis.Warning
                )
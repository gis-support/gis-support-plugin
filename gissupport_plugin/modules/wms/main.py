# -*- coding: utf-8 -*-
from .baza_wms_dialog import BazaWMSDialog
#from .resources import *
from qgis.PyQt.QtWidgets import QTableWidgetItem, QHeaderView
from qgis.core import QgsProject, QgsRasterLayer, Qgis
import json
from os import path
from owslib.wms import WebMapService
import requests.exceptions


class Main:
    module_name = "Baza krajowych usług WMS"

    def __init__(self, iface):

        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.dlg = BazaWMSDialog()

        self.project = QgsProject.instance()
        #Load WMS services list from json file
        with open(path.join(path.dirname(__file__), 'services.json')) as servicesJson:
            self.services = json.load(servicesJson)
        #Initialize table headers
        self.dlg.servicesTableWidget.setHorizontalHeaderLabels(['ID', 'Źródło', 'Nazwa', 'URL'])
        self.dlg.servicesTableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.dlg.layersTableWidget.setHorizontalHeaderLabels(['Nr', 'Nazwa', 'Tytuł', 'Streszczenie', 'Układ współrzędnych'])
        self.dlg.layersTableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

        #Connect slots to signals
        self.dlg.servicesTableWidget.currentItemChanged.connect(self.showDescription)
        self.dlg.searchTextEdit.textChanged.connect(self.updateServicesList)
        self.dlg.getLayersButton.clicked.connect(self.loadLayers)
        self.dlg.layersTableWidget.itemSelectionChanged.connect(self.enableAddToMap)
        self.dlg.addLayersButton.clicked.connect(self.addToMap)

        self.updateServicesList()

    def updateServicesList(self):
        """ Fills the Table Widget with a list of WMS Services """
        self.dlg.servicesTableWidget.setRowCount(0)
        self.dlg.servicesTableWidget.clearContents()
        self.dlg.descriptionTextEdit.clear()
        servicesList = {}
        search = self.dlg.searchTextEdit.toPlainText()
        if search:
            for id, info in self.services.items():
                if search.lower() in info['name'].lower():
                    servicesList.update({ id : info })
        else:
            servicesList = self.services
        for i, wms in enumerate(servicesList.items()):
            id, info = wms
            self.dlg.servicesTableWidget.insertRow(i)
            self.dlg.servicesTableWidget.setItem(i, 0, QTableWidgetItem(id))
            self.dlg.servicesTableWidget.setItem(i, 1, QTableWidgetItem(info['source']))
            self.dlg.servicesTableWidget.setItem(i, 2, QTableWidgetItem(info['name']))
            self.dlg.servicesTableWidget.setItem(i, 3, QTableWidgetItem(info['url']))

    def showDescription(self):
        self.dlg.layersTableWidget.setRowCount(0)
        self.dlg.layersTableWidget.clearContents()
        curRow = self.dlg.servicesTableWidget.currentRow()
        if curRow != -1:
            curServiceId = self.dlg.servicesTableWidget.item(curRow, 0).text()
            self.curServiceData = self.services[curServiceId]
            self.dlg.descriptionTextEdit.setPlainText(self.curServiceData['description'])

    def loadLayers(self):
        self.dlg.layersTableWidget.setRowCount(0)
        defaultCrs = 'EPSG:2180'
        try:
            wmsCapabilities = WebMapService(self.curServiceData['url'])
        except AttributeError:
            wmsCapabilities = WebMapService(self.curServiceData['url'], version='1.3.0')
        except requests.exceptions.ReadTimeout:
            self.iface.messageBar().pushMessage(
                'Baza krajowych usług WMS',
                'Serwer WMS nie odpowiada. Spróbuj ponownie później.',
                level=Qgis.Critical
            )
            return 1
        except requests.exceptions.SSLError:
            self.iface.messageBar().pushMessage(
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
                    self.dlg.layersTableWidget.item(layerId, 1).text(),
                    self.curServiceData['url']
                )
            )
            wmsLayer = QgsRasterLayer(url, self.dlg.layersTableWidget.item(layerId, 2).text(), 'wms')
            if wmsLayer.isValid():
                QgsProject.instance().addMapLayer(wmsLayer)
            else:
                self.iface.messageBar().pushMessage(
                    'Baza krajowych usług WMS',
                    'Nie udało się wczytać warstwy %s' % self.dlg.layersTableWidget.item(layerId, 2).text(),
                    level=Qgis.Warning
                )
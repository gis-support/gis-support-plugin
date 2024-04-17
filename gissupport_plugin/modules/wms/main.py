# -*- coding: utf-8 -*-
import owslib.crs
from qgis._core import QgsVectorLayer

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
from owslib.wfs import WebFeatureService
import requests.exceptions
import urllib
from owslib.etree import ParseError
from owslib.util import ServiceException


class Main(BaseModule):
    module_name = "Baza krajowych usług WMS/WFS"

    def __init__(self, parent):
        super().__init__(parent)
        
        self.canvas = iface.mapCanvas()
        self.dlg = BazaWMSDialog()
        self.curServiceData = None
        self.layerType = None

        self.project = QgsProject.instance()
        #Load WMS services list from json file
        with open(path.join(path.dirname(__file__), 'services.json'), encoding='utf-8') as servicesJson:
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
        self.dlg.servicesTableView.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.dlg.servicesTableView.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.dlg.servicesTableView.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.dlg.servicesTableView.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.dlg.servicesTableView.horizontalHeader().resizeSection(1, 100)
        self.dlg.servicesTableView.horizontalHeader().resizeSection(3, 250)

        self.dlg.layersTableWidget.setHorizontalHeaderLabels(['Nr', 'Nazwa', 'Tytuł', 'Streszczenie'])
        self.dlg.layersTableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.dlg.layersTableWidget.setColumnCount(4)
        self.dlg.layersTableWidget.setColumnWidth(0, 20)
        self.dlg.layersTableWidget.setColumnWidth(1, 70)
        self.dlg.layersTableWidget.setColumnWidth(2, 170)
        self.dlg.layersTableWidget.setColumnWidth(3, 170)
        self.dlg.layersTableWidget.setColumnWidth(4, 90)

        self.dlg.layerTypeCb.addItems(["WMS/WFS", "WMS", "WFS"])

        #Connect slots to signals
        self.dlg.searchLineEdit.textChanged.connect(servicesProxyModel.setFilterRegExp)
        self.dlg.getLayersButton.clicked.connect(self.loadLayers)
        self.dlg.servicesTableView.doubleClicked.connect(self.loadLayers)
        self.dlg.layersTableWidget.itemSelectionChanged.connect(self.enableAddToMap)
        self.dlg.layersTableWidget.doubleClicked.connect(self.addToMap)
        self.dlg.addLayersButton.clicked.connect(self.addToMap)
        self.dlg.layerTypeCb.currentIndexChanged.connect(self.changeLayerTypeCb)

        self.updateServicesList()
        
        #Zarejestrowanie we wtyczce

        self.dlg.lblInfo.setPixmap(QPixmap(':/plugins/plugin/info.png'))
        self.dlg.lblInfo.setToolTip((
            "Brakuje adresu WMS, którego szukasz?\n"
            "Napisz do nas: info@gis-support.pl"))
        
        self.parent.add_action(
            ":/plugins/gissupport_plugin/wms/wms.svg",
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

    def loadLayers(self):
        self.avaliableCrses = None
        self.dlg.layersTableWidget.setRowCount(0)
        row = self.dlg.servicesTableView.selectionModel().selectedRows()
        if len(row) > 0:
            selected = row[0]
            self.curServiceData = selected.sibling(selected.row(), selected.column()).data(role=Qt.UserRole)

            if self.curServiceData['type'] == 'WMS':
                self.layerType = "WMS"
                try:
                    wmsCapabilities = WebMapService(self.curServiceData['url'])
                except (AttributeError, ParseError):
                    wmsCapabilities = WebMapService(self.curServiceData['url'], version='1.3.0')
                except requests.exceptions.ReadTimeout:
                    iface.messageBar().pushMessage(
                        'Baza krajowych usług WMS',
                        'Serwer WMS nie odpowiada. Spróbuj ponownie później.',
                        level=Qgis.Critical
                    )
                    return 1
                except (requests.exceptions.SSLError, ServiceException):
                    iface.messageBar().pushMessage(
                        'Baza krajowych usług WMS',
                        'Błąd połączenia z serwerem WMS.',
                        level=Qgis.Critical
                    )
                    return 1

                formatOptions = wmsCapabilities.getOperationByName('GetMap').formatOptions
                self.populateFormatCb(formatOptions)

                for nr, layer in enumerate(list(wmsCapabilities.contents)):
                    wmsLayer = wmsCapabilities[layer]
                    if nr == 0:
                        self.populateCrsCb(wmsLayer.crsOptions)

                    self.dlg.layersTableWidget.insertRow(nr)
                    self.dlg.layersTableWidget.setItem(nr, 0, QTableWidgetItem(str(nr+1)))
                    self.dlg.layersTableWidget.setItem(nr, 1, QTableWidgetItem(wmsLayer.name))
                    self.dlg.layersTableWidget.setItem(nr, 2, QTableWidgetItem(wmsLayer.title))
                    self.dlg.layersTableWidget.setItem(nr, 3, QTableWidgetItem(wmsLayer.abstract))
            elif self.curServiceData['type'] == 'WFS':
                self.layerType = "WFS"
                try:
                    wfsCapabilities = WebFeatureService(self.curServiceData['url'])
                except (AttributeError, ParseError, TypeError):
                    wfsCapabilities = WebFeatureService(self.curServiceData['url'], version='2.0.0')
                except requests.exceptions.ReadTimeout:
                    iface.messageBar().pushMessage(
                        'Baza krajowych usług WFS',
                        'Serwer WFS nie odpowiada. Spróbuj ponownie później.',
                        level=Qgis.Critical
                    )
                    return 1
                except (requests.exceptions.SSLError, ServiceException):
                    iface.messageBar().pushMessage(
                        'Baza krajowych usług WFS',
                        'Błąd połączenia z serwerem WFS.',
                        level=Qgis.Critical
                    )
                    return 1

                formatOptions = wfsCapabilities.getOperationByName('GetFeature').formatOptions

                self.populateFormatCb(formatOptions)

                for nr, layer in enumerate(list(wfsCapabilities.contents)):
                    wfsLayer = wfsCapabilities[layer]
                    if nr == 0:
                        self.populateCrsCb([code.getcode() for code in wfsLayer.crsOptions])

                    self.dlg.layersTableWidget.insertRow(nr)
                    self.dlg.layersTableWidget.setItem(nr, 0, QTableWidgetItem(str(nr+1)))
                    self.dlg.layersTableWidget.setItem(nr, 1, QTableWidgetItem(wfsLayer.id))
                    self.dlg.layersTableWidget.setItem(nr, 2, QTableWidgetItem(wfsLayer.title))
                    self.dlg.layersTableWidget.setItem(nr, 3, QTableWidgetItem(wfsLayer.abstract))
                return 1

    def enableAddToMap(self):
        layerSelected = True if self.dlg.layersTableWidget.selectionModel().selectedRows() else False
        self.dlg.addLayersButton.setEnabled(layerSelected)

    def addToMap(self):
        selectedRows = [i.row() for i in self.dlg.layersTableWidget.selectionModel().selectedRows()]
        if self.layerType == 'WMS':
            for layerId in selectedRows:
                url = (
                    "contextualWMSLegend=0&"
                    "crs={}&"
                    "dpiMode=7&"
                    "featureCount=10&"
                    "format={}&"
                    "layers={}&"
                    "styles=&"
                    "url={}".format(
                        self.dlg.crsCb.currentText(),
                        self.dlg.formatCb.currentText(),
                        urllib.parse.quote(self.dlg.layersTableWidget.item(layerId, 1).text(), '/:'),
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

        elif self.layerType == 'WFS':
            for layerId in selectedRows:
                url = (
                        "{}?"
                        "SERVICE=WFS&"
                        "REQUEST=GetFeature&"
                        "SRSNAME={}&"
                        "VERSION=2.0.0&"
                        "TYPENAME={}").format(
                            self.curServiceData['url'],
                            self.dlg.crsCb.currentText(),
                            urllib.parse.quote(self.dlg.layersTableWidget.item(layerId, 1).text(), '/:'),
                    )

                wfsLayer = QgsVectorLayer(url, self.dlg.layersTableWidget.item(layerId, 2).text(), 'wfs')

                if wfsLayer.isValid():
                    QgsProject.instance().addMapLayer(wfsLayer)
                else:
                    iface.messageBar().pushMessage(
                        'Baza krajowych usług WFS',
                        'Nie udało się wczytać warstwy %s' % self.dlg.layersTableWidget.item(layerId, 2).text(),
                        level=Qgis.Warning
                    )

    def populateCrsCb(self, crses):
        self.dlg.crsCb.clear()
        default = 'EPSG:2180'
        project_crs = QgsProject.instance().crs().authid()
        if project_crs:
            crses.insert(0, project_crs)
        elif default in crses:
            crses.insert(0, crses.pop(crses.index(default)))

        for index, crs in enumerate(crses, start=1):
            if self.dlg.crsCb.findText(crs) == -1:
                self.dlg.crsCb.insertItem(index, crs)

    def populateFormatCb(self, formats):
        self.dlg.formatCb.clear()
        if self.layerType == 'WMS':
            self.dlg.formatLabel.show()
            self.dlg.formatCb.show()

            default = 'image/png'

            if default not in formats:
                formats.insert(0, default)
            else:
                formats.insert(0, formats.pop(formats.index(default)))

            for index, format in enumerate(formats):
                self.dlg.formatCb.insertItem(index, format)
        else:
            self.dlg.formatLabel.hide()
            self.dlg.formatCb.hide()

    def changeLayerTypeCb(self):
        index = self.dlg.layerTypeCb.currentIndex()
        self.servicesTableModel.removeRows()
        if index == 1:
            services = [service for service in self.services if service['type'] == 'WMS']
            self.servicesTableModel.insertRows(0, services)
        elif index == 2:
            services = [service for service in self.services if service['type'] == 'WFS']
            self.servicesTableModel.insertRows(0, services)
        else:
            self.servicesTableModel.insertRows(0, self.services)

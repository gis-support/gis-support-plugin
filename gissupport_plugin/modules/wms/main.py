# -*- coding: utf-8 -*-
from .baza_wms_dialog import BazaWMSDialog
#from .resources import *
from qgis.PyQt.QtWidgets import QTableWidgetItem, QHeaderView
from qgis.core import QgsProject
import json
from os import path


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

        #Connect slots to signals
        self.dlg.servicesTableWidget.currentItemChanged.connect(self.showDescription)
        self.dlg.searchTextEdit.textChanged.connect(self.updateServicesList)

        self.updateServicesList()

    def updateServicesList(self):
        """ Fills the Table Widget with a list of WMS Services """
        self.dlg.servicesTableWidget.clearContents()
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
        curRow = self.dlg.servicesTableWidget.currentRow()
        curServiceId = self.dlg.servicesTableWidget.item(curRow, 0).text()
        self.dlg.descriptionTextEdit.setPlainText(self.services[curServiceId]['description'])

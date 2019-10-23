# -*- coding: utf-8 -*-
from .baza_wms_dialog import BazaWMSDialog
#from .resources import *
from qgis.PyQt.QtWidgets import QTableWidgetItem, QHeaderView, QAbstractItemView
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
            self.services = json.load(servicesJson)['services']
        #Initialize table headers
        self.dlg.servicesTableWidget.setHorizontalHeaderLabels(['ID', 'Źródło', 'Nazwa', 'URL'])
        self.dlg.servicesTableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.dlg.servicesTableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.dlg.servicesTableWidget.verticalHeader().setVisible(False)

        self.updateServicesList()

    def updateServicesList(self):
        """ Fills the Table Widget with a list of WMS Services """
        self.dlg.servicesTableWidget.clearContents()
        for i, wms in enumerate(self.services):
            self.dlg.servicesTableWidget.insertRow(i)
            self.dlg.servicesTableWidget.setItem(i, 0, QTableWidgetItem(str(wms['id'])))
            self.dlg.servicesTableWidget.setItem(i, 1, QTableWidgetItem(wms['source']))
            self.dlg.servicesTableWidget.setItem(i, 2, QTableWidgetItem(wms['name']))
            self.dlg.servicesTableWidget.setItem(i, 3, QTableWidgetItem(wms['url']))
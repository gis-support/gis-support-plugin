# -*- coding: utf-8 -*-
from .baza_wms_dialog import BazaWMSDialog
#from .resources import *
from qgis.core import QgsProject


class Main:
    module_name = "Baza krajowych usług WMS"

    def __init__(self, iface):

        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.dlg = BazaWMSDialog()

        self.project = QgsProject.instance()
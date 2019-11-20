import json
import locale
import operator
import os
import sys
import time
from collections import OrderedDict
from urllib.request import urlopen

from PyQt5.QtCore import (QCoreApplication, QSettings, Qt, QTranslator,
                          QVariant, qVersion)
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QAction, QShortcut
from qgis.core import *
from qgis.gui import QgsMessageBar

from .modules.csv_import.main import CSVImport
from .modules.map_point_search.main import MapPointSearch
from .modules.point_layer_import.main import PointLayerImport
from .modules.teryt_search.main import TerytSearch
from .plugin_dockwidget import wyszukiwarkaDzialekDockWidget
from .resources import resources
from .uldk.resultcollector import (ResultCollectorMultiple,
                                   ResultCollectorSingle)



class Main:
    module_name = "Wyszukiwarka działek ewidencyjnych (GUGiK ULDK)"    

    def __init__(self, iface, dockwidget = None):

        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.dockwidget = dockwidget or wyszukiwarkaDzialekDockWidget()
        # self.menu = self.tr(PLUGIN_NAME)
        # self.toolbar = self.iface.addToolBar(PLUGIN_NAME)
        # self.toolbar.setObjectName(PLUGIN_NAME)

        self.teryt_search_result_collector = ResultCollectorSingle(self)
        self.map_point_search_result_collector = self.teryt_search_result_collector
        
        self.project = QgsProject.instance()
        self.wms_layer = None
        self.module_csv_import = None
        self.module_teryt_search = None
        self.module_point_layer_import = None
        self.module_wms_kieg_initialized = False
        self.module_map_point_search = MapPointSearch(self, self.teryt_search_result_collector)

        icon = QIcon(":/plugins/gissupport_plugin/uldk/intersect.png")
        self.identifyAction = QAction(icon=icon, parent=self.dockwidget)
        self.identifyAction.setCheckable(True)
        self.identifyAction.toggled.connect(
            lambda state: self.module_map_point_search.toggle(not state)
        )
        self.dockwidget.btnIdentify.setDefaultAction(self.identifyAction)

        result_collector_factory = lambda parent, target_layer: ResultCollectorMultiple(self, target_layer)
        self.module_teryt_search = TerytSearch(self,
            self.dockwidget.tab_teryt_search_layout,
            self.teryt_search_result_collector,
            result_collector_factory,
            ResultCollectorMultiple.default_layer_factory)
        self.module_teryt_search.lpis_bbox_found.connect(self.add_wms_lpis)

        result_collector_factory = lambda parent, target_layer: ResultCollectorMultiple(self, target_layer)
        self.module_csv_import = CSVImport(self,
            self.dockwidget.tab_import_csv_layout, 
            result_collector_factory,
            ResultCollectorMultiple.default_layer_factory)

        self.module_point_layer_import = PointLayerImport(
            self,
            self.dockwidget.tab_import_layer_point_layout)

        self.wms_kieg_layer = None
        self.dockwidget.button_wms_kieg.clicked.connect(self.add_wms_kieg)
        self.module_wms_kieg_initialized = True

        self.wms_lpis_layer = None
        self.dockwidget.button_wms_lpis.clicked.connect(self.add_wms_lpis)
        self.module_wms_lpis_initialized = True
        
    def add_wms_kieg(self):
        
        if self.wms_kieg_layer is None:
            url = ("contextualWMSLegend=0&"
                    "crs=EPSG:2180&"
                    "dpiMode=7&"
                    "featureCount=10&"
                    "format=image/png&"
                    "layers=dzialki&layers=numery_dzialek&"
                    "styles=&styles=&"
                    "version=1.1.1&"
                    "url=http://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow")
            layer = QgsRasterLayer(url, 'Krajowa Integracja Ewidencji Gruntów', 'wms')
            layer.setCustomProperty("ULDK", "wms_kieg_layer")
            self.wms_kieg_layer = layer
            self.project.addMapLayer(self.wms_kieg_layer)
            self.project.layerWillBeRemoved[QgsMapLayer].connect(self.before_layer_removed)
            self.dockwidget.button_wms_kieg.setEnabled(False)
        else:
            self.canvas.refresh()

    def add_wms_lpis(self):
        
        if self.wms_lpis_layer is None:
            url = ( "contextualWMSLegend=0&crs=EPSG:4326&dpiMode=7&featureCount=10&format=image/png&layers=dzialki&styles&url=https://lpis.mapawms.pl/geoserver/lpis/wms")
            layer = QgsRasterLayer(url, "Działki LPIS", "wms")
            layer.setCustomProperty("ULDK", "wms_lpis_layer")
            layer.setMinimumScale(6000)
            layer.setScaleBasedVisibility(True)
            self.wms_lpis_layer = layer
            self.project.addMapLayer(self.wms_lpis_layer)
            self.project.layerWillBeRemoved[QgsMapLayer].connect(self.before_layer_removed)
            self.dockwidget.button_wms_lpis.setEnabled(False)
        else:
            self.canvas.refresh()

    def before_layer_removed(self, layer):
        if layer.customProperty("ULDK") == "wms_lpis_layer":
            self.wms_lpis_layer = None
            self.dockwidget.button_wms_lpis.setEnabled(True)
        if layer.customProperty("ULDK") == "wms_kieg_layer":
            self.wms_kieg_layer = None
            self.dockwidget.button_wms_kieg.setEnabled(True)


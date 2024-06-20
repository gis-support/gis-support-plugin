

from PyQt5.QtCore import Qt
from PyQt5.QtGui import *
from qgis.core import *
from qgis.utils import iface

from gissupport_plugin.modules.base import BaseModule
from gissupport_plugin.modules.uldk.modules.check_layer.main import CheckLayer
from gissupport_plugin.modules.uldk.modules.csv_import.main import CSVImport
from gissupport_plugin.modules.uldk.modules.map_point_search.main import MapPointSearch
from gissupport_plugin.modules.uldk.modules.layer_import.main import LayerImport
from gissupport_plugin.modules.uldk.modules.teryt_search.main import TerytSearch
from gissupport_plugin.modules.uldk.plugin_dockwidget import wyszukiwarkaDzialekDockWidget
from gissupport_plugin.modules.uldk.resources import resources
from gissupport_plugin.modules.uldk.uldk.resultcollector import (ResultCollectorMultiple,
                                ResultCollectorSingle)


class Main(BaseModule):
    module_name = "Wyszukiwarka działek ewidencyjnych"    

    def __init__(self, parent):
        super().__init__(parent)

        self.canvas = iface.mapCanvas()
        self.dockwidget = wyszukiwarkaDzialekDockWidget()
        # self.menu = self.tr(PLUGIN_NAME)
        # self.toolbar = self.iface.addToolBar(PLUGIN_NAME)
        # self.toolbar.setObjectName(PLUGIN_NAME)

        self.teryt_search_result_collector = ResultCollectorSingle(self)
        self.map_point_search_result_collector = self.teryt_search_result_collector
        
        self.project = QgsProject.instance()
        self.wms_layer = None
        self.module_csv_import = None
        self.module_teryt_search = None
        self.module_layer_import = None
        self.module_wms_kieg_initialized = False
        self.module_map_point_search = MapPointSearch(self, self.teryt_search_result_collector)

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

        self.module_layer_import = LayerImport(
            self,
            self.dockwidget.tab_import_layer_layout)

        self.check_layer_result_collector = ResultCollectorSingle(self)
        self.module_layer_check = CheckLayer(self,
            self.dockwidget.tab_check_layer_layout,
            self.teryt_search_result_collector)


        self.wms_kieg_layer = None
        self.module_wms_kieg_initialized = True

        self.wms_lpis_layer = None
        self.module_wms_lpis_initialized = True
        
        icon_info_path = ':/plugins/plugin/info.png'
        self.dockwidget.label_info_map_point_search.setPixmap(QPixmap(icon_info_path))
        self.dockwidget.label_info_map_point_search.setToolTip((
            "Wybierz narzędzie i kliknij na mapę.\n"
            "Narzędzie wyszuka działkę, w której zawierają się współrzędne kliknięcia."))

        #Zarejestrowanie we wtyczce

        iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)

        self.uldk_toolbar_action = self.parent.add_action(
            ":/plugins/gissupport_plugin/uldk/uldk.svg",
            self.module_name,
            lambda state: self.dockwidget.setHidden(not state),
            checkable = True,
            parent = iface.mainWindow(),
            add_to_topmenu=True
        )

        self.dockwidget.visibilityChanged.connect(self.uldk_toolbar_action.setChecked)

        self.identify_action = self.parent.add_action(
            ":/plugins/gissupport_plugin/uldk/uldk_identify.svg",
            text = "Identifykacja ULDK",
            callback = lambda toggle: iface.mapCanvas().setMapTool( self.module_map_point_search ),
            parent = iface.mainWindow(),
            checkable = True,
            add_to_topmenu=False
        )
        self.module_map_point_search.setAction( self.identify_action )
        self.parent.toolbar.addSeparator()

        self.dockwidget.btnIdentify.setDefaultAction(self.identify_action)

        self.dockwidget.hide()

    def unload(self):
        """ Wyłączenie modułu """
        iface.removeDockWidget(self.dockwidget)

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
        else:
            self.canvas.refresh()

    def add_wms_lpis(self):
        
        if self.wms_lpis_layer is None:
            url = (
                'contextualWMSLegend=0&'
                'crs=EPSG:4326&'
                'dpiMode=7&'
                'featureCount=10&'
                'format=image/png&'
                'layers=02&layers=04&layers=06&layers=10&layers=08&layers=12&layers=14&layers=16&layers=18&layers=20&layers=22&layers=24&layers=26&layers=28&layers=30&layers=32&'
                '{}'
                'url=http://integracja.gugik.gov.pl/cgi-bin/arimr_lpis/'
            ).format('styles&' * 16)
            layer = QgsRasterLayer(url, "Działki LPIS", "wms")
            layer.setCustomProperty("ULDK", "wms_lpis_layer")
            layer.setMinimumScale(6000)
            layer.setScaleBasedVisibility(True)
            self.wms_lpis_layer = layer
            self.project.addMapLayer(self.wms_lpis_layer)
            self.project.layerWillBeRemoved[QgsMapLayer].connect(self.before_layer_removed)
        else:
            self.canvas.refresh()

    def before_layer_removed(self, layer):
        if layer.customProperty("ULDK") == "wms_lpis_layer":
            self.wms_lpis_layer = None
        if layer.customProperty("ULDK") == "wms_kieg_layer":
            self.wms_kieg_layer = None


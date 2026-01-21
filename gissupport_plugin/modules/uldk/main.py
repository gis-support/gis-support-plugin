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
from gissupport_plugin.modules.uldk.modules.from_csv_file.main import FromCSVFile
from gissupport_plugin.modules.uldk.plugin_dockwidget import wyszukiwarkaDzialekDockWidget
from gissupport_plugin.modules.uldk.uldk.resultcollector import ResultCollectorSingle

class Main(BaseModule):
    module_name = "Wyszukiwarka działek ewidencyjnych"

    def __init__(self, parent):
        super().__init__(parent)

        self.canvas = iface.mapCanvas()
        self.dockwidget = wyszukiwarkaDzialekDockWidget()

        collector = ResultCollectorSingle(self)

        self.project = QgsProject.instance()
        self.module_map_point_search = MapPointSearch(self, collector)

        self.module_teryt_search = TerytSearch(
            self,
            self.dockwidget.tab_teryt_search_layout,
            collector)

        self.module_csv_import = CSVImport(
            self,
            self.dockwidget.tab_import_csv_layout)

        self.module_layer_import = LayerImport(
            self,
            self.dockwidget.tab_import_layer_layout)

        self.module_from_csv_file = FromCSVFile(
            self,
            self.dockwidget.tab_from_csv_file_layout)

        self.module_layer_check = CheckLayer(self,
            self.dockwidget.tab_check_layer_layout,
            collector)

        icon_info_path = ':/plugins/plugin/info.png'
        self.dockwidget.label_info_map_point_search.setPixmap(QPixmap(icon_info_path))
        self.dockwidget.label_info_map_point_search.setToolTip((
            "Wybierz narzędzie i kliknij na mapę.\n"
            "Narzędzie wyszuka działkę, w której zawierają się współrzędne kliknięcia."))

        self.dockwidget.labelLayerInfo.setPixmap(QPixmap(icon_info_path))
        #Zarejestrowanie we wtyczce

        iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)

        self.uldk_toolbar_action = self.parent.add_dockwidget_action(
            dockwidget=self.dockwidget,
            icon_path=':/plugins/gissupport_plugin/uldk/uldk.svg',
            text=self.module_name,
            add_to_topmenu=True
        )

        self.identify_action = self.parent.add_action(
            ":/plugins/gissupport_plugin/uldk/uldk_identify.svg",
            text = "Identifykacja ULDK",
            callback = self.toggle_map_point_search_tool,
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

    def toggle_map_point_search_tool(self, checked):
        """
        Włącza/wyłącza narzędzie identyfikacji działek w zależności od stanu akcji.
        """
        if checked:
            iface.mapCanvas().setMapTool(self.module_map_point_search)
        else:
            iface.mapCanvas().unsetMapTool(self.module_map_point_search)

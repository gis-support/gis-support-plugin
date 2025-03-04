import os

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWebKitWidgets import QWebView    
from PyQt5.QtGui import QIcon, QDesktopServices
from qgis.PyQt.QtCore import QUrl

from PyQt5.Qt import QStandardItemModel, QStandardItem, QSortFilterProxyModel
from qgis.utils import iface
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject

from gissupport_plugin.modules.gis_box.layers.layers_registry import layers_registry
from gissupport_plugin.tools.logger import Logger
from gissupport_plugin.modules.gis_box.gui.login_settings import LoginSettingsDialog
from gissupport_plugin.tools.gisbox_connection import GISBOX_CONNECTION


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'gisbox_dockwidget.ui'))


class GISBoxDockWidget(QtWidgets.QDockWidget, FORM_CLASS, Logger):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super(GISBoxDockWidget, self).__init__(parent)
        self.setupUi(self)
        self.loginSettingsDialog = LoginSettingsDialog(self)


        # przyciski na górze widgetu
        self.connectButton.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/widget_connect.svg"))
        self.connectButton.setCheckable(True)

        self.authSettingsButton.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/widget_settings.svg"))
        self.authSettingsButton.clicked.connect(self.show_login_settings)
        

        # zakładka Dane
        self.refreshButton.clicked.connect(self.refresh_layer)
        self.refreshButton.setEnabled(False)

        self.refreshButton.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/refresh.svg"))
        self.layerTreeView.doubleClicked.connect(self.add_layer_to_map)
        self.layerTreeView.setDragEnabled(True)

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setRecursiveFilteringEnabled(True)

        self.layerBrowser.textChanged.connect(self.filter_tree_view)

        layers_registry.on_schema.connect(self.add_layers_to_treeview)


    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()


    def filter_tree_view(self, text):
        self.proxy_model.setFilterFixedString(text)
        
        if text:
            self.layerTreeView.expandAll()
        else:
            self.layerTreeView.collapseAll()

    def show_login_settings(self):
        """ Wyświetlenie okna ustawień logowania """
        self.loginSettingsDialog.show()

    def toggle_visibility(self):
        if self.isVisible():
            iface.removeDockWidget(self)
        else:
            iface.addDockWidget(Qt.RightDockWidgetArea, self)
    
    def add_layer_to_map(self, index):
        source_index = self.proxy_model.mapToSource(index)
        source_model = self.proxy_model.sourceModel()
        item = source_model.itemFromIndex(source_index)

        if group_data := item.data(Qt.UserRole + 2):
            layers_registry.loadGroup(group_data)

        elif layer_class := item.data(Qt.UserRole + 1):
            layer_class.loadLayer()

    def add_layers_to_treeview(self, groups: list):

        modules_layer_custom_id = -99
        tree_model = QStandardItemModel()
        
        self.proxy_model.setSourceModel(tree_model)

        root_item = tree_model.invisibleRootItem()

        def add_layers(layers: list, group_item: QStandardItem):

            if not layers:
                return

            for layer_id in layers:
                layer_class = layers_registry.layers.get(layer_id)

                if layer_class:
                    if hasattr(layer_class, 'datasource'):
                        if layer_class.datasource_name == 'foreign_vehicles':
                            continue

                    layer_item = QStandardItem(layer_class.name)
                    layer_item.setData(layer_class, Qt.UserRole + 1)
                
                    group_item.appendRow(layer_item)

        def add_groups(groups: list):
            for group in groups:
                group_layers = group.get('layers')
                if not group_layers:
                    continue

                if group['id'] == modules_layer_custom_id:
                    continue

                scope = group['schema_scope']
                if scope == 'core':
                    group_item = QStandardItem(group['name'])
                    group_item.setData([group['name'], group['id']], Qt.UserRole + 2)
                    add_layers(group_layers, group_item)
                    root_item.appendRow(group_item)


        add_groups(groups)
        self.layerTreeView.setModel(self.proxy_model)
        self.layerTreeView.setHeaderHidden(True)
        self.layerTreeView.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.message('Pobrano schemat warstw')

    def clear_treeview(self):
        if self.proxy_model.sourceModel():
            self.proxy_model.sourceModel().clear()
        else:
            self.layerTreeView.setModel(None)

    def refresh_layer(self):
        if not GISBOX_CONNECTION.is_connected:
            return
        for layer in QgsProject.instance().mapLayers().values():
            if layers_registry.isGisboxLayer(layer):
                layer_id = layer.customProperty('gisbox/layer_id')
                layer_class = layers_registry.layers.get(int(layer_id))
                if not layer_class:
                    return
                layer_class.on_reload.emit(True)

    def open_url(self, url):
        """ Otwarcie linku w przeglądarce """
        QDesktopServices.openUrl(QUrl(url))

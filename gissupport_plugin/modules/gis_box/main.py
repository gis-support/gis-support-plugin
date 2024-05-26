from PyQt5.QtCore import Qt
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QToolButton, QMenu
from qgis.utils import iface
from qgis.core import QgsProject

from gissupport_plugin.modules.base import BaseModule
from gissupport_plugin.modules.gis_box.modules.auto_digitization.gui.widget import AutoDigitizationWidget
from gissupport_plugin.tools.gisbox_connection import GISBOX_CONNECTION
from gissupport_plugin.modules.gis_box.layers.layers_registry import layers_registry
from gissupport_plugin.tools.logger import Logger
from gissupport_plugin.modules.gis_box.gui.login_settings import LoginSettingsDialog

class GISBox(BaseModule, Logger):

    def __init__(self, parent):
        super().__init__(parent)
        self.parent.toolbar.addSeparator()
        self.loginSettingsDialog = LoginSettingsDialog(self)

        self.gisboxAction = self.parent.add_action(
            icon_path=":/plugins/gissupport_plugin/gis_box/disconnected.png",
            text = 'GIS.Box',
            callback=lambda: None,
            parent=iface.mainWindow(),
            add_to_menu=False,
            add_to_topmenu=False,
            add_to_toolbar=True,
            checkable=False,
            enabled=True
        )

        self.connectAction = self.parent.add_action(
            icon_path=":/plugins/gissupport_plugin/gis_box/connected.svg",
            text='Połącz z GIS.Box',
            callback=self.onConnection,
            parent=iface.mainWindow(),
            add_to_menu=False,
            add_to_topmenu=False,
            add_to_toolbar=False,
            checkable=True,
            enabled=True
        )
        self.connectAction.setCheckable(True)

        # Projekty
        self.addLayersAction = self.parent.add_action(
            icon_path=':/plugins/gissupport_plugin/gis_box/dodaj_warstwy.svg',
            text='Dane',
            callback=lambda: None,
            parent=iface.mainWindow(),
            add_to_menu=False,
            add_to_topmenu=False,
            add_to_toolbar=False,
            checkable=False,
            enabled=False
        )
        
        self.refreshLayerAction = self.parent.add_action(
            icon_path=':/plugins/gissupport_plugin/gis_box/refresh.svg',
            text='Odśwież warstwy',
            callback=self.refreshLayer,
            parent=iface.mainWindow(),
            add_to_menu=False,
            add_to_topmenu=False,
            add_to_toolbar=False,
            checkable=False,
            enabled=False
        )

        self.autoDigitalizationAction = self.parent.add_action(
            icon_path=':/plugins/gissupport_plugin/gis_box/digitization.svg',
            text='Automatyczna wektoryzacja',
            callback=self.autoDigitization,
            parent=iface.mainWindow(),
            add_to_menu=False,
            add_to_topmenu=False,
            add_to_toolbar=False,
            checkable=False,
            enabled=False
        )

        # Ustawienia logowania
        self.loginSettingsAction = self.parent.add_action(
            None,
            text='Ustawienia logowania',
            callback=self.showLoginSettings,
            parent=iface.mainWindow(),
            add_to_menu=False,
            add_to_topmenu=False,
            add_to_toolbar=False,
            checkable=False,
            enabled=True
        )

        # Link do strony QGIS + GIS.Box = <3
        self.qgisPlusGisboxAction = self.parent.add_action(
            None,
            text='QGIS + GIS.Box = \u2764',
            callback=lambda: self.open_url("https://gis-support.pl/qgis-gis-box/"),
            parent=iface.mainWindow(),
            add_to_menu=False,
            add_to_topmenu=False,
            add_to_toolbar=False,
            checkable=False,
            enabled=True
        )

        # Link do strony o GIS.Box
        self.aboutGisboxAction = self.parent.add_action(
            None,
            text='O GIS.Box',
            callback=lambda: self.open_url("https://gis-support.pl/gis-box/"),
            parent=iface.mainWindow(),
            add_to_menu=False,
            add_to_topmenu=False,
            add_to_toolbar=False,
            checkable=False,
            enabled=True
        )

        self._create_gisbox_list()
        self.toolButton = self.parent.toolbar.widgetForAction(self.gisboxAction)
        self.toolButton.setPopupMode(QToolButton.InstantPopup)
        layers_registry.on_schema.connect(self._create_layers_menu)
        layers_registry.on_schema.connect(self.readProject)
        QgsProject.instance().readProject.connect(self.readProject)

    def _create_gisbox_list(self):
        """ Tworzenie listy ustawień GIS.Box """
        self.gisboxAction.setMenu(QMenu())
        main_menu = self.gisboxAction.menu()

        main_menu.addAction(self.connectAction)
        main_menu.addAction(self.addLayersAction)
        main_menu.addAction(self.refreshLayerAction)
        main_menu.addAction(self.autoDigitalizationAction)

        main_menu.addSeparator()
        main_menu.addAction(self.loginSettingsAction)
        main_menu.addSeparator()

        main_menu.addAction(self.qgisPlusGisboxAction)
        main_menu.addAction(self.aboutGisboxAction)

    def onConnection(self, connect: bool):
        """ Połączenie/rozłączenie z serwerem """
        connected = connect and GISBOX_CONNECTION.connect()

        self.loginSettingsAction.setEnabled( not connected )

        if connected:
            # Połączono z serwerem
            self.gisboxAction.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/connected.png"))
            self.connectAction.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/connection.svg"))
            self.connectAction.setText('Rozłącz z GIS.Box')
            self.refreshLayerAction.setEnabled(True)

            GISBOX_CONNECTION.get(
                "/api/settings/automatic_digitization_module_enabled?value_only=true", callback=self.enableDigitization
            )

        else:
            # Rozłączono z serwerem lub błąd połączenia
            self.gisboxAction.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/disconnected.png"))
            self.connectAction.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/connected.svg"))
            self.connectAction.setText('Połącz z GIS.Box')
            self._clear_data()
            self.connectAction.setChecked(False)
            self.refreshLayerAction.setEnabled(False)
            self.autoDigitalizationAction.setEnabled(False)

    def _create_layers_menu(self, groups: list):
        modules_layer_custom_id = -99

        self.addLayersAction.setMenu(QMenu())
        main_menu = self.addLayersAction.menu()

        def add_layers(layers: list, menu: QMenu, group_id: int = None):
            if not layers:
                return
            if group_id is not None:
                action = menu.addAction(
                    'Dodaj wszystkie warstwy z grupy')
                action.setData(group_id)
                action.triggered.connect(layers_registry.loadGroup)
            menu.addSeparator()
            for layer_id in layers:
                layer_class = layers_registry.layers.get(layer_id)
                if layer_class:
                    if hasattr(layer_class, 'datasource'):
                        if layer_class.datasource_name == 'foreign_vehicles':
                            continue
                    action = menu.addAction(layer_class.name)
                    action.setCheckable(True)
                    action.triggered.connect(layer_class.loadLayer)
                    layer_class.parent = action

        def add_groups(groups: list, menu: QMenu):
            for group in groups:
                group_layers = group.get('layers')
                if not group_layers:
                    continue

                if group['id'] == modules_layer_custom_id:
                    continue

                scope = group['schema_scope']
                if scope == 'core':
                    sub_menu = main_menu.addMenu(group['name'])
                    add_layers(group_layers, sub_menu, group['id'])

        add_groups(groups, main_menu)
        self.addLayersAction.setEnabled(True)
        self.message('Pobrano schemat warstw')
        
    def _clear_data(self):
        """ Czyszczenie danych po rozłączeniu z serwerem """
        self.addLayersAction.setMenu(None)
        self.addLayersAction.setEnabled(False)

    def readProject(self):
        if not GISBOX_CONNECTION.is_connected:
            return
        for layer in QgsProject.instance().mapLayers().values():
            if layers_registry.isGisboxLayer(layer):
                layer_class = layers_registry.layers[int(
                    layer.customProperty('gisbox/layer_id'))]
                layer_class.setLayer(layer, from_project=True)
                
    def refreshLayer(self):
        if not GISBOX_CONNECTION.is_connected:
            return
        for layer in QgsProject.instance().mapLayers().values():
            if layers_registry.isGisboxLayer(layer):
                layer_id = layer.customProperty('gisbox/layer_id')
                layer_class = layers_registry.layers.get(int(layer_id))
                if not layer_class:
                    return
                layer_class.on_reload.emit(True)

    def autoDigitization(self):
        self.dockwidget = AutoDigitizationWidget()
        iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)

    def showLoginSettings(self):
        """ Wyświetlenie okna ustawień logowania """
        self.loginSettingsDialog.show()

    def open_url(self, url):
        """ Otwarcie linku w przeglądarce """
        QDesktopServices.openUrl(QUrl(url))

    def enableDigitization(self, data):
        if data["data"]:
            self.autoDigitalizationAction.setEnabled(True)

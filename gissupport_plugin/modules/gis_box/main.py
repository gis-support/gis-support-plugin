import time
from typing import List
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QToolButton, QMenu
from qgis.utils import iface

from gissupport_plugin.modules.base import BaseModule
from gissupport_plugin.tools.gisbox_connection import GISBOX_CONNECTION
from gissupport_plugin.modules.gis_box.layers.layers_registry import layers_registry

class GISBox(BaseModule):

    def __init__(self, parent):
        super().__init__(parent)
        self.parent.toolbar.addSeparator()

        self.connectAction = self.parent.add_action(
            icon_path=":/plugins/gissupport_plugin/gis_box/connection.svg",
            text='Połącz z GIS.Box',
            callback=self.onConnection,
            parent=iface.mainWindow(),
            add_to_menu=False,
            add_to_topmenu=False,
            add_to_toolbar=True,
            checkable=True,
            enabled=True
        )
        self.connectAction.setCheckable(True)

        # Projekty
        self.addLayersAction = self.parent.add_action(
            icon_path=':/plugins/gissupport_plugin/gis_box/dodaj_warstwy.svg',
            text='Wczytaj projekt',
            callback=lambda: None,
            parent=iface.mainWindow(),
            add_to_menu=False,
            add_to_topmenu=False,
            add_to_toolbar=True,
            checkable=False,
            enabled=False
        )
        self.parent.toolbar.addSeparator()
        self.toolButton = self.parent.toolbar.widgetForAction(self.addLayersAction)
        self.toolButton.setPopupMode(QToolButton.InstantPopup)
        layers_registry.on_schema.connect(self._create_layers_menu)

    def onConnection(self, connect: bool):
        """ Połączenie/rozłączenie z serwerem """
        connected = connect and GISBOX_CONNECTION.connect()

        self.parent.loginSettingsAction.setEnabled( not connected )
        self.addLayersAction.setEnabled( connected )

        if connected and GISBOX_CONNECTION.connect():
            # Połączono z serwerem
            self.connectAction.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/connected.svg"))
        else:
            # Rozłączono z serwerem lub błąd połączenia
            self.connectAction.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/connection.svg"))
            self._clear_data()
            self.connectAction.setChecked(False)

    def _create_layers_menu(self, groups: list):
        modules_layer_custom_id = -99

        self.addLayersAction.setMenu(QMenu())
        main_menu = self.addLayersAction.menu()

        scope_menus = self._get_scope_menus(main_menu)

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
                scope_menu = scope_menus.get(scope)
                if scope_menu:
                    sub_menu = scope_menu.addMenu(group['name'])
                    add_layers(group_layers, sub_menu, group['id'])

        def add_module_layers():
            module_layers_group = layers_registry.getGroupById(
                modules_layer_custom_id)
            if module_layers_group:
                module_layers = module_layers_group.get('layers')
            module_menu = scope_menus['module']
            add_layers(module_layers, module_menu, modules_layer_custom_id)

        add_groups(groups, main_menu)
        add_module_layers()
        self.addLayersAction.setEnabled(True)

    def _clear_data(self):
        """ Czyszczenie danych po rozłączeniu z serwerem """
        self.addLayersAction.setMenu(None)

    def _get_modules(self) -> List:
        response = GISBOX_CONNECTION.get(
            f'/api/license_manager/modules?cache={time.time()}', sync=True)
        modules_data = response['data']
        on_modules = [module['name'] for module in modules_data
                      if module['configured'] and module['enabled']]
        return on_modules
    
    def _get_scope_menus(self, main_menu: QMenu) -> dict:
        scope_menus = {
            'core': main_menu.addMenu('Warstwy ogólne'),
        }
        modules = self._get_modules()
        if 'WATER_DATA' in modules:
            scope_menus['water'] = main_menu.addMenu('Warstwy wodociągowe')
        if 'SEWER_DATA' in modules:
            scope_menus['sewer'] = main_menu.addMenu('Warstwy kanalizacyjne')
        if 'MASTERPLAN_SQUARES' in modules:
            scope_menus['masterplan_squares'] = main_menu.addMenu('Masterplan - Place')
        if 'MASTERPLAN_STREETS' in modules:
            scope_menus['masterplan_streets'] = main_menu.addMenu('Masterplan - Ulice')
        if 'MASTERPLAN_ILLUMINATION' in modules:
            scope_menus['masterplan_illumination'] = main_menu.addMenu('Masterplan - Obiekty do iluminacji')
        scope_menus['module'] = main_menu.addMenu('Warstwy modułów dodatkowych')
        return scope_menus
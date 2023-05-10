import time

from qgis.PyQt.QtCore import pyqtSignal, QObject
from qgis.core import QgsProject
from qgis.utils import iface

from . import RELATION_VALUES_MAPPING_REGISTRY

from .basemap_layer import BaseMapLayer
from .gisbox_datasource import GisboxFeatureLayer

from gissupport_plugin.tools.logger import Logger
from gissupport_plugin.tools.gisbox_connection import GISBOX_CONNECTION

class LayersRegistry(QObject, Logger):
    """ Klasa służy do zarządzania warstwami gisbox """

    on_schema = pyqtSignal(list)
    on_layers = pyqtSignal(dict)
    data_loaded = pyqtSignal()
    on_groups = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        # Dane inicjalne
        self.groups = [{'id': -99, 'schema_scope': 'module',
                        'name': 'Warstwy modułów dodatkowych',
                        'subgroups': []}]
        self.layers = {}
        self.baselayers = {}

        # Sygnały
        # Po połączeniu pobieramy dane
        GISBOX_CONNECTION.on_connect.connect(self.loadData)
        self.on_layers.connect(self.onLayers)

    def loadData(self, connected: bool):
        """ Załadowanie wszystkich danych """
        if not connected:
            return
        # Wyczyszczenie wcześniejszych danych
        self.groups = [{'id': -99, 'schema_scope': 'module',
                        'name': 'Warstwy modułów dodatkowych',
                        'subgroups': []}]
        self.layers = {}
        self.baselayers = {}
        self.message('Pobieranie schematu warstw...', duration=10)
        GISBOX_CONNECTION.get(
            '/api/dataio/data_sources/relation_values_mapping/all', callback=self._set_relation_values_mapping)
        GISBOX_CONNECTION.get(
            f'/api/qgis/layers/schema?cache={time.time()}', callback=self.on_layers.emit)

    def onLayers(self, data: dict):
        """ Zapamiętanie pobranych warstw i pobranie warstw podkładowych """
        layers = data['data']['layers']
        self.groups.extend(data['data']['groups'])

        for layer in layers:
            self._put_layer_in_group(layer)
            if layer['type'] == 'service_layer':
                if not layer.get('service_layers_names'):
                    continue
                current_layer = BaseMapLayer(layer)
            else:
                current_layer = GisboxFeatureLayer(layer)
            self.layers[current_layer.id] = current_layer
        self.on_schema.emit(self.groups)

    def _set_relation_values_mapping(self, data: dict):
        RELATION_VALUES_MAPPING_REGISTRY.update(data['data'])

    def _put_layer_in_group(self, layer):
        layer_group_id = layer['group_id']
        if layer_group_id is None and layer['layer_scope'] == 'module':
            layer_group_id = -99

        group = self.getGroupById(layer_group_id)

        if group:
            if group.get('layers'):
                # Sprawdzamy czy warstwa nie jest już w grupie
                if layer['id'] in group['layers']:
                    return
                group['layers'].append(layer['id'])
            else:
                group['layers'] = [layer['id']]

    def getGroupById(self, group_id, groups=None):
        if groups is None:
            groups = self.groups
        for group in groups:
            if group['id'] == group_id:
                return group
            subgroup = self.getGroupById(group_id, group['subgroups'])
            if subgroup is not None and subgroup['id'] == group_id:
                return subgroup

    def isGisboxLayer(self, layer=None):
        """ Sprawdza czy dana warstwa jest warstwą GISBox """
        if layer is None:
            # Jeśli nie podano warstwy to sprawdzamy warstwę aktywną
            layer = iface.activeLayer()
        if layer is None:
            # Brak warstw
            return False
        return bool(layer.customProperty('gisbox/is_gisbox_layer'))

    def getLayerClass(self, layer=None):
        """ Zwraca klasę danej warstwy """
        if layer is None:
            # Jeśli nie podano warstwy to sprawdzamy warstwę aktywną
            layer = iface.activeLayer()
        if not self.isGisboxLayer(layer):
            # To nie jest warstwa gisbox
            return
        return layers_registry.layers.get(int(layer.customProperty('gisbox/layer_id')))

    def loadGroup(self):
        action = self.sender()
        group_id = action.data()
        group = self.getGroupById(group_id)
        group_name = action.parent().title()

        root = QgsProject.instance().layerTreeRoot()
        qgis_group = root.addGroup(group_name)
        for layer_id in group['layers']:
            layer_class = self.layers.get(layer_id)
            if layer_class:
                layer_class.loadLayer(group=qgis_group)
        iface.mapCanvas().refresh()


# Stworzenie instancji klasy
layers_registry = LayersRegistry()

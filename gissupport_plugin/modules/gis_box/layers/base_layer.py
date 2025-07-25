# coding: utf-8
from qgis.core import (QgsCoordinateTransform, QgsCoordinateReferenceSystem,
                       QgsProject, QgsMapLayer)
from qgis.utils import iface
from qgis.PyQt.QtCore import QObject

from gissupport_plugin.tools.logger import Logger


class BaseLayer(QObject, Logger):
    """ Klasa bazowa dla wszystkich typów warstw gisbox """

    def __init__(self, data: dict, parent, layer_type=None, layers=[]):
        super(BaseLayer, self).__init__(parent)

        self.parent = parent
        # Lista warstw dla danego typu
        self.layers = []
        self.first = False
        # Metadane warstwy
        self.id = data.get('id')
        self.group_id = data.get('group_id')
        self.display_name = data['name']
        self.srid = data.get('srid', 2178)
        self.layer_type = layer_type
        self.permissions = data.get('permission_value')

        # Warstwy bez nazwy tabeli są warstwami rastrowymi lub innymi
        self.tablename = None

        if layers:
            for layer in layers:
                self.setLayer(layer)

    def setLayer(self, layer=None):
        """ Rejestracja warstwy QGIS """
        if layer and not QgsProject.instance().layerTreeRoot().findLayers():
            self.first = True
        else:
            self.first = False
        if isinstance(self.sender(), QgsMapLayer):
            # Usunięcie warstwy z TOC
            try:
                self.layers.remove(self.sender())
            except ValueError:
                del self.layers[0]
            self.log(self.layers)
            self.unregisterLayer(self.sender())
        if not layer:
            return
        # Ustawienia warstwy
        layer.setCustomProperty("skipMemoryLayersCheck", 1)
        layer.setCustomProperty('gisbox/layer_id', self.id)
        layer.setCustomProperty('gisbox/layer_type', self.layer_type)
        # Zarejestrowanie warstwy
        self.layers.append(layer)
        self.registerLayer(layer)

    def registerLayer(self, layer):
        """ Zarejestrowanie warstwy """
        # Odznaczenie pozycji w menu w przypadku usunięcia warstwy z QGIS
        layer.willBeDeleted.connect(self.setLayer)
        self.checkLayer(True)
        # Usunięcie z legendy ikony warstwy tymczasowej
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        indicators = iface.layerTreeView().indicators(node)
        if indicators:
            iface.layerTreeView().removeIndicator(node, indicators[0])

    def unregisterLayer(self, layer):
        """ Wyrejestrowanie warstwy """
        if not self.layers:
            self.checkLayer(False)
        try:
            layer.willBeDeleted.disconnect(self.setLayer)
        except Exception as e:
            self.log(e)

    def checkLayer(self, state):
        try:
            self.parent.setChecked(state)
        except:
            pass

    def zoomToExtent(self, layer):
        """ Przybiżenie do warstwy z innym układem współrzędnych """
        # Przybliżamy tylko do pierwszej dodanej warstwy
        if not self.first:
            return
        if layer.crs().authid() != QgsProject.instance().crs().authid():
            extent = layer.extent()
            fromCrs = QgsCoordinateReferenceSystem(layer.crs().authid())
            toCrs = QgsCoordinateReferenceSystem(
                QgsProject.instance().crs().authid())
            transformation = QgsCoordinateTransform(
                fromCrs, toCrs, QgsProject.instance())
            extent = transformation.transform(extent)
        else:
            extent = layer.extent()
        iface.mapCanvas().setExtent(extent.scaled(1.1))
        layer.triggerRepaint()

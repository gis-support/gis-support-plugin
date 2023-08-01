#coding: UTF-8

from qgis.core import QgsProject, QgsRasterLayer, QgsLayerTreeLayer, QgsVectorLayer
from qgis.utils import iface
from owslib.wmts import WebMapTileService
from owslib.wms import WebMapService
from owslib.etree import ParseError

from .base_layer import BaseLayer


class BaseMapLayer(BaseLayer):
    """ Klasa warstw map bazowych """

    def __init__(self, data: dict, parent=None, layer_type=None, layers=None):
        super(BaseMapLayer, self).__init__(data, parent, layer_type, layers)

        self.name = data['name']
        service_layers_list = data.get('service_layers_names')
        self.service_layers_names = ','.join(service_layers_list)
        self.type = data.get('service_type', 'wms')
        self.zmax = data.get('zoomMax', 21)
        self.zmin = data.get('zoomMin', 10)
        self.epsg = self.getEpsg(data.get('parameters'))

        if self.type == 'xyz':
            # Dla OSM wskazujemy konkretną subdomenę, zamieniamy też znaki specjalne na hexy
            url = data['url'].replace(
                '{a-c}', 'a').replace("=", "%3D").replace("&", "%26")
            self.url = f'type={self.type}&url={url}&zmax=19&zmin=0'
        else:
            self.url = data['url'].replace("=", "%3D").replace("&", "%26")

        # self.setLayer(layer)

    def wmtsUrl(self):
        """ Budowanie adresu dla WMTS """
        cap = WebMapTileService(self.url)
        layer = cap.contents[self.service_layers_names]
        crs = self.getCrs(layer.tilematrixsetlinks)
        style = self.getStyle(layer.styles)
        layer_format = self.getFormat(layer.formats)
        url = f"contextualWMSLegend=0&crs={crs}&dpiMode=7&featureCount=10&format={layer_format}&layers={self.service_layers_names}&styles={style}&tileMatrixSet={crs}&url={self.url}"
        if 'mapy.geoportal.gov.pl' in self.url:
            # Geoportal oczywiście musi mieć własne rozkminy
            url += '?service%3Dwmts%26request%3DgetCapabilities'
        return url

    def wmsUrl(self):
        """ Budowanie adresu dla WMS """
        try:
            cap = WebMapService(self.url)
        except (AttributeError, ParseError):
            cap = WebMapService(self.url, version='1.3.0')
        names = self.service_layers_names.split(',')
        layer = cap.contents[names[0]]
        crs = self.getCrs(layer.crsOptions)
        style = self.getStyle(layer.styles)
        layers = '&layers='.join(names)
        styles = '&styles='.join([style]*len(names))
        layer_format = self.getFormat(
            cap.getOperationByName('GetMap').formatOptions)
        url = f'contextualWMSLegend=0&crs={crs}&dpiMode=7&featureCount=10&format={layer_format}&layers={layers}&styles={styles}&url={self.url}'
        return url

    def getEpsg(self, parameters):
        """ Układ współrzędnych """
        if not parameters:
            return 'EPSG:2180'
        if 'EPSG' in parameters:
            return f"EPSG:{parameters['EPSG']}"
        if 'CRS' in parameters:
            return parameters['CRS']
        if 'SRS' in parameters:
            return parameters['SRS']
        # Jak nic nie znaleziono to przyjmujemy układ PUWG2180
        return 'EPSG:2180'

    def getCrs(self, crsList):
        """ Układ współrzędnych dla WMS/WMST """
        # Brak układów do wyszukania
        if not crsList:
            return self.epsg
        # Układ projektu
        project_crs = QgsProject.instance().crs().authid()
        if project_crs in crsList:
            return project_crs
        # Układ z ustawień
        if self.epsg in crsList:
            return self.epsg
        # Układ PUWG1992
        if 'EPSG:2180' in crsList:
            return 'EPSG:2180'
        # Pierwszy dostępny
        return crsList[0]

    def getStyle(self, styles):
        """ Styl """
        # Najpierw wyszukujemy domyślnego stylu
        for name, style in styles.items():
            if style.get('isDefault', False):
                return name
        # Teraz próbujmey nazwę 'default'
        if 'default' in styles:
            return 'default'
        # Nic nie znaleziono
        return ''

    def getFormat(self, formats):
        """ Format danych """
        if not formats or 'image/png' in formats:
            return 'image/png'
        if 'image/jpeg' in formats:
            return 'image/jpeg'
        return formats[0]

    def loadLayer(self, checked=False, group=None):
        """ Załadowanie mapy """
        if self.layers:
            layer = self.layers[0].clone()
        else:
            if self.type == 'wmts':
                url = self.wmtsUrl()
            elif self.type == 'wms':
                url = self.wmsUrl()
            else:
                url = self.url
            layer = QgsRasterLayer(url, self.name, 'wms')
        self.setLayer(layer)
        QgsProject.instance().addMapLayer(layer, False)
        if group is None:
            QgsProject.instance().layerTreeRoot().insertChildNode(-1, QgsLayerTreeLayer(layer))
        else:
            group.addLayer(layer)
        self.deleteTemporaryIcons(layer)

    def deleteTemporaryIcons(self, layer):
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        indicators = iface.layerTreeView().indicators(node)
        if indicators:
            iface.layerTreeView().removeIndicator(node, indicators[0])
# coding: utf-8

from osgeo.ogr import CreateGeometryFromJson
from qgis.core import QgsGeometry
import json


def geojson2geom(geojson: dict) -> QgsGeometry:
    """ Konwersja geometrii GeoJSON na QgsGeometry """
    # Najpierw musimy uzyskać format pośredni, który obsługuje QGIS
    # WKB jest najszybsze
    if not geojson:
        geojson = "null" # od QGIS 3.40 wywala błąd w momencie gdy geometria jest typu None
    wkb = CreateGeometryFromJson(json.dumps(geojson)).ExportToWkb()
    # Stworzenie nowej geometrii QgsGeometry
    geometry = QgsGeometry()
    geometry.fromWkb(wkb)
    return geometry

from PyQt5.QtCore import QVariant
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsCoordinateTransformContext, QgsFeature, QgsGeometry,
                       QgsPointXY, QgsWkbTypes)

crs_2180 = QgsCoordinateReferenceSystem.fromEpsgId(2180)

def extract_lpis_bbox(lpis_response, target_crs, response_crs = crs_2180):

    response_points = lpis_response["geometry"]["coordinates"][0]

    wkt = "POLYGON (({}))"

    wkt_points = []
    for point in response_points:
        wkt_point = "{} {}".format(*point)
        wkt_points.append(wkt_point)

    wkt_points_str = ", ".join(wkt_points)
    wkt = wkt.format(wkt_points_str)

    response_bbox = QgsGeometry().fromWkt(wkt)
    
    transformation = QgsCoordinateTransform(response_crs, target_crs, QgsCoordinateTransformContext())
    target_bbox = transformation.transformBoundingBox(response_bbox.boundingBox())

    return target_bbox

from PyQt5.QtCore import QObject, QThread, QVariant, pyqtSignal, pyqtSlot
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsCoordinateTransformContext, QgsField, QgsGeometry,
                       QgsPoint, QgsVectorLayer, QgsFeature, QgsWkbTypes,
                       QgsProject, QgsDistanceArea, QgsFields)

from ...uldk.api import ULDKSearchPoint, ULDKSearchLogger, ULDKPoint

PLOTS_LAYER_DEFAULT_FIELDS = [
    QgsField("wojewodztwo", QVariant.String),
    QgsField("powiat", QVariant.String),
    QgsField("gmina", QVariant.String),
    QgsField("obreb", QVariant.String),
    QgsField("arkusz", QVariant.String),
    QgsField("nr_dzialki", QVariant.String),
    QgsField("teryt", QVariant.String),
    QgsField("pow_m2", QVariant.String),
]

CRS_2180 = QgsCoordinateReferenceSystem.fromEpsgId(2180)

class BadGeometryException(Exception):
    pass


def uldk_response_to_qgs_feature(response_row, additional_attributes = []):
    def get_sheet(teryt):
        split = teryt.split(".")
        if len(split) == 4:
            return split[2]
        else:
            return None

    geom_wkt, province, county, municipality, precinct, plot_id, teryt = \
        response_row.split("|")

    sheet = get_sheet(teryt)
    
    ewkt = geom_wkt.split(";")
    if len(ewkt) == 2:
        geom_wkt = ewkt[1]

    geometry = QgsGeometry.fromWkt(geom_wkt)
    area = geometry.area()

    if not geometry.isGeosValid():
        geometry = geometry.makeValid()
        if not geometry.isGeosValid():
            raise BadGeometryException()

    feature = QgsFeature()
    feature.setGeometry(geometry)
    attributes = [province, county, municipality, precinct, sheet, plot_id, teryt, area]
    attributes += additional_attributes
    feature.setAttributes(attributes)

    return feature


class LayerImportWorker(QObject):

    finished = pyqtSignal(QgsVectorLayer, QgsVectorLayer)
    interrupted = pyqtSignal(QgsVectorLayer, QgsVectorLayer)
    progressed = pyqtSignal(QgsVectorLayer, QgsVectorLayer, bool, int, bool, bool)

    def __init__(self, source_layer, selected_only, layer_name, additional_output_fields=None):
        super().__init__()
        self.source_layer = source_layer
        self.selected_only = selected_only
        self.additional_output_fields = additional_output_fields if additional_output_fields else []

        self.layer_found = QgsVectorLayer(f"Polygon?crs=EPSG:{2180}", layer_name, "memory")
        self.layer_found.setCustomProperty("ULDK", f"{layer_name} point_import_found")

        self.layer_not_found = QgsVectorLayer(f"Point?crs=EPSG:{2180}", f"{layer_name} (nieznalezione)", "memory")
        self.layer_not_found.setCustomProperty("ULDK", f"{layer_name} point_import_not_found")

    @pyqtSlot()
    def search(self):
        fields = PLOTS_LAYER_DEFAULT_FIELDS + self.additional_output_fields

        self.layer_found.startEditing()
        self.layer_found.dataProvider().addAttributes(fields)

        self.layer_not_found.startEditing()
        self.layer_not_found.dataProvider().addAttributes([
            QgsField("tresc_bledu", QVariant.String),
        ])

        self.uldk_search = ULDKSearchPoint(
            "dzialka",
            ("geom_wkt", "wojewodztwo", "powiat", "gmina", "obreb","numer","teryt"))

        self.uldk_search = ULDKSearchLogger(self.uldk_search)

        feature_iterator = self.source_layer.getSelectedFeatures() if self.selected_only else self.source_layer.getFeatures()
        source_geom_type = self.source_layer.wkbType()
        source_crs = self.source_layer.sourceCrs()
        self.geometries = []
        self.not_found_geometries = []
        self.parcels_geometry = QgsGeometry.fromMultiPolygonXY([])

        self.transformation = None
        if source_crs != CRS_2180:
            self.transformation = QgsCoordinateTransform(source_crs, CRS_2180, QgsCoordinateTransformContext())

        geom_type = QgsWkbTypes.flatType(source_geom_type)
        if geom_type == QgsWkbTypes.Point or geom_type == QgsWkbTypes.MultiPoint:
            self.count_not_found_as_progressed = True

            for index, f in enumerate(feature_iterator):
                point = f.geometry().asPoint()

                if self.transformation:
                    point = self.transformation.transform(point)

                f.setGeometry(QgsGeometry.fromPointXY(point))
                self._process_feature(f, True)
        else:
            self.count_not_found_as_progressed = False

            if self.additional_output_fields:
                self.fields_to_add = QgsFields()
                for field in self.additional_output_fields:
                    self.fields_to_add.append(field)

            for f in feature_iterator:
                additional_attributes = []

                if self.additional_output_fields:
                    additional_attributes = [f.attribute(field.name()) for field in self.additional_output_fields]

                points = self._feature_to_points(f, source_geom_type, additional_attributes)
                continue_search = True

                while points != []:
                    # saved_features = [self._process_feature(point) for point in points]
                    saved_features = []
                    for point_number, point in enumerate(points, start=1):
                        last_point = True if point_number == len(points) else False
                        saved_features.append(self._process_feature(point, last_feature=last_point))
                    if any(saved_features):
                        points = self._feature_to_points(f, source_geom_type, additional_attributes)
                    else:
                        points = []
                self.__commit()
                self.progressed.emit(self.layer_found, self.layer_not_found, True, 0, False, True)

        self.finished.emit(self.layer_found, self.layer_not_found)

    def __make_not_found_feature(self, geometry, e):
        error_message = str(e)
        feature = QgsFeature()
        feature.setGeometry(geometry)
        feature.setAttributes([error_message])

        return feature

    def __commit(self):
        self.layer_found.commitChanges()
        self.layer_not_found.commitChanges()

    def _process_feature(self, source_feature, made_progress=False, last_feature=False):

        if QThread.currentThread().isInterruptionRequested():
            self.__commit()
            self.interrupted.emit(self.layer_found, self.layer_not_found)
            self.layer_found.stopEditing()
            return

        point = source_feature.geometry().asPoint()
        if self.parcels_geometry.contains(point):
            if made_progress:
                self.__commit()
                self.progressed.emit(self.layer_found, self.layer_not_found, True, 1, False, made_progress)
            return

        uldk_point = ULDKPoint(point.x(), point.y(), 2180)
        found_parcels_geometries = []
        saved = False

        try:
            uldk_response_row = self.uldk_search.search(uldk_point)
            additional_attributes = []
            for field in self.additional_output_fields:
                additional_attributes.append(source_feature[field.name()])
            try:
                found_feature = uldk_response_to_qgs_feature(uldk_response_row, additional_attributes)
                geometry_wkt = found_feature.geometry().asWkt()
            except BadGeometryException:
                raise BadGeometryException("Niepoprawna geometria")
            if geometry_wkt not in self.geometries:
                saved = True
                self.layer_found.dataProvider().addFeature(found_feature)
                self.geometries.append(geometry_wkt)
                found_parcels_geometries.append(found_feature.geometry().asPolygon())
                self.progressed.emit(self.layer_found, self.layer_not_found, True, 0, saved, made_progress)
        except Exception as e:
            geometry = source_feature.geometry()
            geometry_wkt = geometry.asWkt()
            if geometry_wkt not in self.not_found_geometries:
                not_found_feature = self.__make_not_found_feature(geometry, e)
                self.layer_not_found.dataProvider().addFeature(not_found_feature)
                self.not_found_geometries.append(geometry_wkt)
                if last_feature:
                    self.progressed.emit(self.layer_found, self.layer_not_found, False, 0, saved, made_progress)


        self.parcels_geometry.addPartGeometry(QgsGeometry.fromMultiPolygonXY(found_parcels_geometries))
        self.__commit()
        return saved

    def _feature_to_points(self, feature, geom_type, additional_attributes):
        geometry = feature.geometry()

        geometry = geometry.coerceToType(QgsWkbTypes.flatType(geometry.wkbType()))[0]

        features = []
        points_number = 0

        if self.transformation is not None:
            geometry.transform(self.transformation)

        if geom_type in (QgsWkbTypes.LineString, QgsWkbTypes.MultiLineString):
            points_number = 10
            geometry = geometry.buffer(0.001, 2)

        if self.parcels_geometry:
            if self.parcels_geometry.contains(geometry):
                return []
            else:
                if not geometry.isMultipart():
                    geometry.convertToMultiType()

                diff_geometry = geometry.difference(self.parcels_geometry.buffer(0.001, 2))

                # obsługa przypadku, gdy różnicą poligonów jest linia
                if diff_geometry.wkbType() in (QgsWkbTypes.LineString, QgsWkbTypes.MultiLineString):
                    geometry = diff_geometry.buffer(0.001, 5)

                else:
                    geometry = diff_geometry
                if not geometry:
                    return []

        da = QgsDistanceArea()
        da.setSourceCrs(CRS_2180, QgsProject.instance().transformContext())
        da.setEllipsoid(QgsProject.instance().ellipsoid())

        points_number = 20 if not points_number else points_number
        area = int(da.measureArea(geometry))/10000
        if area > 1:
            points_number *= area
        points = geometry.randomPointsInPolygon(int(points_number))

        for point in points:
            feature = QgsFeature()

            if additional_attributes:
                feature.setFields(self.fields_to_add)
                feature.setAttributes(additional_attributes)

            feature.setGeometry(QgsGeometry.fromPointXY(point))
            features.append(feature)

        return features

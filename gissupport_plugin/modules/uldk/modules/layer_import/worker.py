from PyQt5.QtCore import QObject, QThread, QVariant, pyqtSignal, pyqtSlot
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsCoordinateTransformContext, QgsField, QgsGeometry,
                       QgsPointXY, QgsVectorLayer, QgsFeature, QgsWkbTypes,
                       QgsProject, QgsDistanceArea, QgsFields)

from ...uldk.api import ULDKSearchPoint, ULDKSearchLogger, ULDKPoint
from typing import Optional, List, Any

PLOTS_LAYER_DEFAULT_FIELDS = [
    QgsField("wojewodztwo", QVariant.String),
    QgsField("powiat", QVariant.String),
    QgsField("gmina", QVariant.String),
    QgsField("obreb", QVariant.String),
    QgsField("arkusz", QVariant.String),
    QgsField("nr_dzialki", QVariant.String),
    QgsField("teryt", QVariant.String),
    QgsField("pow_m2", QVariant.Double, prec=2),
]

CRS_2180 = QgsCoordinateReferenceSystem.fromEpsgId(2180)

ATTRIBUTE_MAPPING = {
            'wojewodztwo': 'wojewodztwo',
            'woj': 'wojewodztwo',
            'powiat': 'powiat',
            'gmina': 'gmina',
            'obreb': 'obreb',
            'arkusz': 'arkusz',
            'nr_dzialki': 'nr_dzialki',
            'teryt': 'teryt',
            'pow_m2': 'pow_m2'
        }

class BadGeometryException(Exception):
    pass


def uldk_response_to_qgs_feature(response_row: str,
                                 additional_attributes: List[Any] = [],
                                 additional_fields_def: Optional[List[QgsField]] = None) -> QgsFeature:
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
    all_fields = QgsFields()
    for field in PLOTS_LAYER_DEFAULT_FIELDS:
        all_fields.append(field)

    if additional_fields_def:
        for field in additional_fields_def:
            all_fields.append(field)

    feature = QgsFeature()
    feature.setFields(all_fields)
    feature.setGeometry(geometry)
    attributes = [province, county, municipality, precinct, sheet, plot_id, teryt, area]
    attributes += additional_attributes
    feature.setAttributes(attributes)

    return feature


class LayerImportWorker(QObject):

    finished = pyqtSignal(QgsVectorLayer, QgsVectorLayer)
    interrupted = pyqtSignal(QgsVectorLayer, QgsVectorLayer)
    progressed = pyqtSignal(QgsVectorLayer, QgsVectorLayer, bool, int, bool, bool)

    def __init__(self,
                 source_layer: QgsVectorLayer,
                 selected_only: bool,
                 layer_name: str,
                 additional_output_fields: Optional[List[QgsField]] = None,
                 layer_found: Optional[QgsVectorLayer] = None,
                 use_existing_layer: Optional[bool] = None) -> None:
        super().__init__()
        self.source_layer = source_layer
        self.selected_only = selected_only
        self.additional_output_fields = additional_output_fields if additional_output_fields else []
        self.use_existing_layer = use_existing_layer

        # Warstwa dla znalezionych działek
        if layer_found:
            # Używamy istniejącej warstwy
            self.layer_found = layer_found
            self._layer_found_is_new = False
        else:
            # Tworzymy nową warstwę
            self.layer_found = QgsVectorLayer(f"Polygon?crs=EPSG:{2180}", layer_name, "memory")
            self.layer_found.setCustomProperty("ULDK", f"{layer_name} point_import_found")
            self._layer_found_is_new = True

        self.layer_not_found = QgsVectorLayer(f"Point?crs=EPSG:{2180}",
                                               f"{layer_name} (nieznalezione)", "memory")
        self.layer_not_found.setCustomProperty("ULDK", f"{layer_name} point_import_not_found")

        self.count_not_found_as_progressed = False

    @pyqtSlot()
    def search(self) -> None:
        self._prepare_layers_for_search()

        source_geom_type = self.source_layer.wkbType()
        geom_type = QgsWkbTypes.flatType(source_geom_type)

        self.count_not_found_as_progressed = (geom_type in (QgsWkbTypes.Point, QgsWkbTypes.MultiPoint))

        self.uldk_search = ULDKSearchLogger(ULDKSearchPoint(
            "dzialka",
            ("geom_wkt", "wojewodztwo", "powiat", "gmina", "obreb","numer","teryt")))

        feature_iterator = self.source_layer.getSelectedFeatures() if self.selected_only else self.source_layer.getFeatures()
        source_crs = self.source_layer.sourceCrs()
        self.geometries = []

        self.transformation = None
        if source_crs != CRS_2180:
            self.transformation = QgsCoordinateTransform(source_crs, CRS_2180, QgsCoordinateTransformContext())

        for f in feature_iterator:
            if QThread.currentThread().isInterruptionRequested():
                break

            geom = f.geometry()
            if self.transformation:
                geom.transform(self.transformation)

            geom_type = QgsWkbTypes.flatType(geom.wkbType())

            if geom_type in (QgsWkbTypes.Polygon, QgsWkbTypes.MultiPolygon):
                self._process_polygon_with_fishnet(f, geom)
                self.progressed.emit(self.layer_found, self.layer_not_found, True, 0, False, True)

            elif geom_type in (QgsWkbTypes.LineString, QgsWkbTypes.MultiLineString):
                self._process_line_with_densification(f, geom)
                self.progressed.emit(self.layer_found, self.layer_not_found, True, 0, False, True)

            elif geom_type in (QgsWkbTypes.Point, QgsWkbTypes.MultiPoint):
                points = geom.asGeometryCollection() if geom.isMultipart() else [geom]
                additional_attributes = [f.attribute(field.name()) for field in self.additional_output_fields]
                for p_geom in points:
                    self._fetch_single_parcel(p_geom.asPoint(), additional_attributes)

                self.progressed.emit(self.layer_found, self.layer_not_found, True, 1, False, True)

        self.finished.emit(self.layer_found, self.layer_not_found)

    def _process_polygon_with_fishnet(self, source_feature: QgsFeature, search_geometry: QgsGeometry):
        step = 1.0
        bbox = search_geometry.boundingBox()
        additional_attributes = [source_feature.attribute(field.name()) for field in self.additional_output_fields]

        curr_x = bbox.xMinimum()
        while curr_x <= bbox.xMaximum():
            curr_y = bbox.yMinimum()
            while curr_y <= bbox.yMaximum():
                if QThread.currentThread().isInterruptionRequested():
                    return

                point = QgsPointXY(curr_x, curr_y)

                if search_geometry.contains(point):
                    found_parcel_geom = self._fetch_single_parcel(point, additional_attributes)

                    if found_parcel_geom:
                        search_geometry = search_geometry.difference(found_parcel_geom.buffer(0.1, 3))

                curr_y += step
            curr_x += step

        if not search_geometry.isEmpty() and search_geometry.area() > 0.5:
            parts = search_geometry.asGeometryCollection() if search_geometry.isMultipart() else [search_geometry]

            for part_geom in parts:
                if QThread.currentThread().isInterruptionRequested() or part_geom.area() < 0.5:
                    continue

                test_point = part_geom.pointOnSurface().asPoint()
                self._fetch_single_parcel(test_point, additional_attributes)

    def _fetch_single_parcel(self, point_xy: QgsPointXY, additional_attributes: list) -> Optional[QgsGeometry]:
        """Odpytywanie API i dodawanie działki do warstwy."""
        try:
            uldk_point = ULDKPoint(point_xy.x(), point_xy.y(), 2180)
            response_row = self.uldk_search.search(uldk_point)

            found_feature = uldk_response_to_qgs_feature(
                response_row,
                additional_attributes=additional_attributes,
                additional_fields_def=self.additional_output_fields
            )

            geom_wkt = found_feature.geometry().asWkt()
            if geom_wkt not in self.geometries:
                if self.use_existing_layer:
                    found_feature = self._map_feature_to_existing_layer(found_feature)

                self.layer_found.dataProvider().addFeatures([found_feature])
                self.geometries.append(geom_wkt)

                self.progressed.emit(self.layer_found, self.layer_not_found, True, 0, True, False)
                return found_feature.geometry()

        except Exception as e:
            geometry = QgsGeometry.fromPointXY(point_xy)
            geometry_wkt = geometry.asWkt()

            if not hasattr(self, 'not_found_geometries'):
                self.not_found_geometries = []

            if geometry_wkt not in self.not_found_geometries:
                not_found_feature = self.__make_not_found_feature(geometry, e)
                self.layer_not_found.dataProvider().addFeatures([not_found_feature])
                self.not_found_geometries.append(geometry_wkt)

                self.progressed.emit(self.layer_found, self.layer_not_found, False, 0, False, False)

        return

    def _prepare_layers_for_search(self):
        """Metoda przygotowująca warstwy i pola"""
        fields = PLOTS_LAYER_DEFAULT_FIELDS + self.additional_output_fields
        if self._layer_found_is_new:
            self.layer_found.startEditing()
            self.layer_found.dataProvider().addAttributes(fields)
            self.layer_found.updateFields()
            self.layer_found.commitChanges()

        self.layer_not_found.startEditing()
        if self.layer_not_found.fields().indexFromName("tresc_bledu") == -1:
            self.layer_not_found.dataProvider().addAttributes([QgsField("tresc_bledu", QVariant.String)])
            self.layer_not_found.updateFields()
        self.layer_not_found.commitChanges()

    def _process_line_with_densification(self, source_feature: QgsFeature, line_geometry: QgsGeometry):
        additional_attributes = [source_feature.attribute(field.name()) for field in self.additional_output_fields]

        current_line = line_geometry.densifyByDistance(1.0)

        max_attempts = 500
        attempts = 0

        while not current_line.isEmpty() and current_line.length() > 0.1 and attempts < max_attempts:
            if QThread.currentThread().isInterruptionRequested():
                return
            attempts += 1

            test_point_geom = current_line.interpolate(0)
            test_point = test_point_geom.asPoint()

            found_parcel_geom = self._fetch_single_parcel(test_point, additional_attributes)

            if found_parcel_geom:
                parcel_buffered = found_parcel_geom.buffer(0.1, 3)
                current_line = current_line.difference(parcel_buffered)
            else:
                skip_buffer = test_point_geom.buffer(2.0, 3)
                current_line = current_line.difference(skip_buffer)

            if not current_line.isGeosValid():
                current_line = current_line.makeValid()

        self.progressed.emit(self.layer_found, self.layer_not_found, True, 1, False, True)

    def __make_not_found_feature(self, geometry, e):
        error_message = str(e)
        feature = QgsFeature()
        feature.setGeometry(geometry)
        feature.setAttributes([error_message])

        return feature

    def __commit(self):
        self.layer_found.commitChanges()
        self.layer_not_found.commitChanges()

    def _process_feature(self,
                         source_feature: QgsFeature,
                         made_progress=False,
                         last_feature=False) -> Optional[bool]:

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
                found_feature = uldk_response_to_qgs_feature(
                    uldk_response_row,
                    additional_fields_def=self.additional_output_fields,
                    additional_attributes=additional_attributes
                    )
                if self.use_existing_layer:
                    found_feature = self._map_feature_to_existing_layer(found_feature)
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

    def _map_feature_to_existing_layer(self, source_feature: QgsFeature) -> QgsFeature:
        new_feat = QgsFeature(self.layer_found.fields())

        geometry = source_feature.geometry()
        target_crs = self.layer_found.crs()

        if CRS_2180 != target_crs:
            transform = QgsCoordinateTransform(CRS_2180, target_crs, QgsProject.instance())
            geometry.transform(transform)

        new_feat.setGeometry(geometry)

        # Mapowanie atrybutów
        target_fields = self.layer_found.fields()
        for target_name, source_name in ATTRIBUTE_MAPPING.items():
            field_idx = target_fields.lookupField(target_name)
            if field_idx != -1:
                new_feat.setAttribute(field_idx, source_feature[source_name])

        # Mapowanie dodatkowych pól
        for field in self.additional_output_fields:
            field_name = field.name()
            target_idx = target_fields.lookupField(field_name)
            if target_idx != -1:
                new_feat.setAttribute(target_idx, source_feature.attribute(field_name))

        return new_feat
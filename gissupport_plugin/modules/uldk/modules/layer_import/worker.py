import os
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

    finished = pyqtSignal(QgsVectorLayer)
    interrupted = pyqtSignal(QgsVectorLayer)
    progressed = pyqtSignal(QgsVectorLayer, bool, int, bool, bool)

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

    @pyqtSlot()
    def search(self) -> None:
        self._prepare_layers_for_search()

        # Wczytanie granic Polski
        boundary_path = os.path.join(os.path.dirname(__file__), "poland_boundary.gpkg")
        boundary_layer = QgsVectorLayer(f"{boundary_path}|layername=poland_boundary", "boundary", "ogr")

        # Wyciągnięcie geometrii granicy Polski
        poland_geom = QgsGeometry()
        if boundary_layer.isValid():
            feat_iter = boundary_layer.getFeatures()
            boundary_feat = next(feat_iter, None)
            if boundary_feat:
                poland_geom = boundary_feat.geometry()

        source_geom_type = self.source_layer.wkbType()
        geom_type = QgsWkbTypes.flatType(source_geom_type)

        self.uldk_search = ULDKSearchLogger(ULDKSearchPoint(
            "dzialka",
            ("geom_wkt", "wojewodztwo", "powiat", "gmina", "obreb", "numer", "teryt")))

        feature_iterator = self.source_layer.getSelectedFeatures() if self.selected_only else self.source_layer.getFeatures()
        source_crs = self.source_layer.sourceCrs()
        self.geometries = [] # Lista już znalezionych działek

        self.transformation = None
        if source_crs != CRS_2180:
            self.transformation = QgsCoordinateTransform(source_crs, CRS_2180, QgsCoordinateTransformContext())

        for f in feature_iterator:
            if QThread.currentThread().isInterruptionRequested():
                break

            geom = f.geometry()
            if self.transformation:
                geom.transform(self.transformation)

            if not poland_geom.isEmpty():
                geom = geom.intersection(poland_geom) # Obcinanie geometrii do granic Polski

                # Jeśli po docięciu obiekt jest poza Polską (pusta geometria), pomijamy go
                if geom.isEmpty():
                    self.progressed.emit(self.layer_found, True, 0, False, True)
                    continue

            geom_type = QgsWkbTypes.flatType(geom.wkbType())

            if geom_type in (QgsWkbTypes.Polygon, QgsWkbTypes.MultiPolygon):
                self._process_polygon_with_fishnet(f, geom)
                self.progressed.emit(self.layer_found, True, 0, False, True)

            elif geom_type in (QgsWkbTypes.LineString, QgsWkbTypes.MultiLineString):
                self._process_line_with_densification(f, geom)
                self.progressed.emit(self.layer_found, True, 0, False, True)

            elif geom_type in (QgsWkbTypes.Point, QgsWkbTypes.MultiPoint):
                points = geom.asGeometryCollection() if geom.isMultipart() else [geom]
                additional_attributes = [f.attribute(field.name()) for field in self.additional_output_fields]
                for p_geom in points:
                    self._fetch_single_parcel(p_geom.asPoint(), additional_attributes)

                self.progressed.emit(self.layer_found, True, 1, False, True)

        self.finished.emit(self.layer_found)

    def _process_polygon_with_fishnet(self, source_feature: QgsFeature, search_geometry: QgsGeometry):
        step = 1.0 # Rozstaw punktów siatki w metrach
        start_area = search_geometry.area()
        if start_area <= 0:
            return

        bbox = search_geometry.boundingBox()
        additional_attributes = [source_feature.attribute(field.name()) for field in self.additional_output_fields]

        # Iterujemy po siatce - od lewej do prawej, od dołu do góry
        curr_x = bbox.xMinimum()
        while curr_x <= bbox.xMaximum():
            curr_y = bbox.yMinimum()
            while curr_y <= bbox.yMaximum():
                if QThread.currentThread().isInterruptionRequested():
                    return

                point = QgsPointXY(curr_x, curr_y)

                # Sprawdzenie czy punkt leży w obszarze który jeszcze nie został przetworzony
                if search_geometry.intersects(QgsGeometry.fromPointXY(point)):
                    # Próba znalezienia działki dla tego punktu
                    found_parcel_geom = self._fetch_single_parcel(point, additional_attributes)

                    if found_parcel_geom:
                        # Odejmujemy działkę z obszaru przeszukiwania (z małym buforem 0.1m)
                        search_geometry = search_geometry.difference(found_parcel_geom.buffer(0.1, 3))
                    else:
                        # Jeśli nie znaleziono, pomijamy okrąg 10m wokół punktu
                        skip_area = QgsGeometry.fromPointXY(point).buffer(10.0, 3)
                        search_geometry = search_geometry.difference(skip_area)

                curr_y += step
            curr_x += step

        # Sprawdzenie czy po przejściu siatką zostały jakieś dziury
        if not search_geometry.isEmpty() and search_geometry.area() > 0.5:
            # Rozbicie na części jeśli multipart
            parts = search_geometry.asGeometryCollection() if search_geometry.isMultipart() else [search_geometry]

            for part_geom in parts:
                if QThread.currentThread().isInterruptionRequested() or part_geom.area() < 0.5:
                    continue
                # Pobieranie punktu wewnątrz fragmentu i próba znalezienia działki
                test_point = part_geom.pointOnSurface().asPoint()
                self._fetch_single_parcel(test_point, additional_attributes)

    def _fetch_single_parcel(self, point_xy: QgsPointXY, additional_attributes: list) -> Optional[QgsGeometry]:
        """Odpytywanie API i dodawanie działki do warstwy."""
        try:
            # Wywołanie API
            response_row = self.uldk_search.search(ULDKPoint(point_xy.x(), point_xy.y(), 2180))

            # Konwersja odpowiedź na feature
            found_feature = uldk_response_to_qgs_feature(
                response_row,
                additional_attributes=additional_attributes,
                additional_fields_def=self.additional_output_fields
            )

            # Sprawdzenie czy to nie duplikat
            geom_wkt = found_feature.geometry().asWkt()
            if geom_wkt not in self.geometries:
                # Jeśli nowa działka, mapujemy do struktury istniejącej warstwy jeśli trzeba
                if self.use_existing_layer:
                    found_feature = self._map_feature_to_existing_layer(found_feature)

                # Dodawanie do warstwy
                self.layer_found.dataProvider().addFeatures([found_feature])
                self.geometries.append(geom_wkt) # Zapamiętywanie WKT żeby unikać duplikatów

                self.progressed.emit(self.layer_found, True, 0, True, False)
                return found_feature.geometry() # Zwracamy geometrię dla dalszego przetwarzania

        except Exception:
            return
        return

    def _prepare_layers_for_search(self):
        """Metoda przygotowująca warstwy i pola"""
        fields = PLOTS_LAYER_DEFAULT_FIELDS + self.additional_output_fields
        if self._layer_found_is_new:
            self.layer_found.startEditing()
            self.layer_found.dataProvider().addAttributes(fields)
            self.layer_found.updateFields() # Odświeża strukturę pól w warstwie
            self.layer_found.commitChanges()

    def _process_line_with_densification(self, source_feature: QgsFeature, line_geometry: QgsGeometry):
        additional_attributes = [source_feature.attribute(field.name()) for field in self.additional_output_fields]

        # Zagęszczamy linię dodajemy wierzchołki co 1m
        current_line = line_geometry.densifyByDistance(1.0)
        attempts = 0

        # Przetwarzamy dopóki linia się nie skończy lub nie osiągniemy limitu prób
        while not current_line.isEmpty() and current_line.length() > 0.1 and attempts < 500:
            if QThread.currentThread().isInterruptionRequested():
                return
            attempts += 1

            # Pobieranie punktu na początku aktualnej linii (odległość = 0)
            test_point_geom = current_line.interpolate(0)
            test_point = test_point_geom.asPoint()

            # Próba znalezienia działki dla tego punktu
            found_parcel_geom = self._fetch_single_parcel(test_point, additional_attributes)

            if found_parcel_geom:
                # Jeśli znaleziono działkę, odejmujemy działkę od linii (z buforem 0.1m)
                parcel_buffered = found_parcel_geom.buffer(0.1, 3)
                current_line = current_line.difference(parcel_buffered)
            else:
                # Jeśli nie, pomijamy mały fragment linii (bufor 2m)
                skip_buffer = test_point_geom.buffer(2.0, 3)
                current_line = current_line.difference(skip_buffer)

            # Naprawiamy geometrię jeśli operacja difference ją zepsuła
            if not current_line.isGeosValid():
                current_line = current_line.makeValid()

        self.progressed.emit(self.layer_found, True, 1, False, True)

    def __commit(self):
        self.layer_found.commitChanges()

    def _process_feature(self,
                         source_feature: QgsFeature,
                         made_progress=False,
                         last_feature=False) -> Optional[bool]:

        if QThread.currentThread().isInterruptionRequested():
            self.__commit()
            self.interrupted.emit(self.layer_found)
            self.layer_found.stopEditing()
            return

        point = source_feature.geometry().asPoint()
        # Sprawdzamy czy punkt nie leży już w znalezionej działce
        if self.parcels_geometry.intersects(QgsGeometry.fromPointXY(point)):
            if made_progress:
                self.__commit()
                self.progressed.emit(self.layer_found, True, 1, False, made_progress)
            return

        found_parcels_geometries = []
        saved = False

        try:
            uldk_response_row = self.uldk_search.search(ULDKPoint(point.x(), point.y(), 2180))
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
            if geometry_wkt not in self.geometries: # Sprawdzamy czy to nie duplikat
                saved = True
                self.layer_found.dataProvider().addFeature(found_feature)
                self.geometries.append(geometry_wkt)
                found_parcels_geometries.append(found_feature.geometry().asPolygon())
                self.progressed.emit(self.layer_found, True, 0, saved, made_progress)
        except Exception:
            # Błąd API lub brak działki - tylko emitujemy sygnał jeśli to ostatni obiekt
            if last_feature:
                self.progressed.emit(self.layer_found, False, 0, saved, made_progress)

        # Dodajemy znalezioną działkę do geometrii już przetworzonych obszarów
        self.parcels_geometry.addPartGeometry(QgsGeometry.fromMultiPolygonXY(found_parcels_geometries))
        self.__commit()
        return saved

    def _feature_to_points(self, feature, geom_type, additional_attributes):
        geometry = feature.geometry()

        # Sprowadzamy do płaskiego typu (bez Z/M)
        geometry = geometry.coerceToType(QgsWkbTypes.flatType(geometry.wkbType()))[0]

        features = []
        points_number = 0

        if self.transformation is not None:
            geometry.transform(self.transformation)

        # Dla linii - najpierw robimy bufor żeby stworzyć poligon
        if geom_type in (QgsWkbTypes.LineString, QgsWkbTypes.MultiLineString):
            points_number = 10
            geometry = geometry.buffer(0.001, 2)

        # Odejmujemy obszary które już zostały przetworzone
        if self.parcels_geometry:
            if self.parcels_geometry.contains(geometry):
                return [] # Cała geometria już przetworzona
            else:
                if not geometry.isMultipart():
                    geometry.convertToMultiType()

                # Obliczamy różnicę (to co jeszcze nie zostało przetworzone)
                diff_geometry = geometry.difference(self.parcels_geometry.buffer(0.001, 2))

                # obsługa przypadku, gdy różnicą poligonów jest linia
                if diff_geometry.wkbType() in (QgsWkbTypes.LineString, QgsWkbTypes.MultiLineString):
                    geometry = diff_geometry.buffer(0.001, 5)

                else:
                    geometry = diff_geometry
                if not geometry:
                    return []

        # Obliczamy powierzchnię żeby dostosować liczbę punktów
        da = QgsDistanceArea()
        da.setSourceCrs(CRS_2180, QgsProject.instance().transformContext())
        da.setEllipsoid(QgsProject.instance().ellipsoid())

        # Bazowo 20 punktów, więcej dla większych obszarów
        points_number = 20 if not points_number else points_number
        area = int(da.measureArea(geometry))/10000 # Powierzchnia w hektarach
        if area > 1:
            points_number *= area # Więcej punktów dla większych obszarów

        # Generujemy losowe punkty wewnątrz geometrii
        points = geometry.randomPointsInPolygon(int(points_number))

        # Tworzymy feature dla każdego punktu
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
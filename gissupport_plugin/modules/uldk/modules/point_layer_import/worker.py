from PyQt5.QtCore import QObject, QThread, QVariant, pyqtSignal, pyqtSlot
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsCoordinateTransformContext, QgsField, QgsGeometry,
                       QgsPoint, QgsVectorLayer, QgsFeature)

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

class PointLayerImportWorker(QObject):

    finished = pyqtSignal(QgsVectorLayer, QgsVectorLayer)
    interrupted = pyqtSignal(QgsVectorLayer, QgsVectorLayer)
    progressed = pyqtSignal(bool, int, bool)
    
    def __init__(self, source_layer, selected_only, layer_name, additional_output_fields = []):
        super().__init__()
        self.source_layer = source_layer
        self.selected_only = selected_only
        self.additional_output_fields = additional_output_fields

        self.layer_found = QgsVectorLayer(f"Polygon?crs=EPSG:{2180}", layer_name, "memory")
        self.layer_found.setCustomProperty("ULDK", f"{layer_name} point_import_found")

        self.layer_not_found = QgsVectorLayer(f"Point?crs=EPSG:{2180}", f"{layer_name} (nieznalezione)", "memory")
        self.layer_not_found.setCustomProperty("ULDK", f"{layer_name} point_import_not_found")

    @pyqtSlot()
    def search(self):
        plots_found = []
        features_not_found = []

        fields = PLOTS_LAYER_DEFAULT_FIELDS + self.additional_output_fields

        self.layer_found.startEditing()
        self.layer_found.dataProvider().addAttributes(fields)
        
        self.layer_not_found.startEditing()
        self.layer_not_found.dataProvider().addAttributes([
            QgsField("tresc_bledu", QVariant.String),
        ])

        features = []
        features_iterator = self.source_layer.getSelectedFeatures() if self.selected_only else self.source_layer.getFeatures()
        source_crs = self.source_layer.sourceCrs()
        if source_crs != CRS_2180:
            transformation = (QgsCoordinateTransform(source_crs, CRS_2180, QgsCoordinateTransformContext()))
            for f in features_iterator:
                point = f.geometry().asPoint()
                point = transformation.transform(point)
                f.setGeometry(QgsGeometry.fromPointXY(point))
                features.append(f)
        else:
            transformation = None
            features = features_iterator

        uldk_search = ULDKSearchPoint(
            "dzialka",
            ("geom_wkt", "wojewodztwo", "powiat", "gmina", "obreb","numer","teryt"))

        uldk_search = ULDKSearchLogger(uldk_search)

        found_features = []
        geometries = []
        for source_feature in features:
            if QThread.currentThread().isInterruptionRequested():
                self.__commit()
                self.interrupted.emit(self.layer_found, self.layer_not_found)
                return

            point = source_feature.geometry().asPoint()
            uldk_point = ULDKPoint(point.x(), point.y(), 2180)
            try:
                uldk_response_row = uldk_search.search(uldk_point)
                additional_attributes = []
                for field in self.additional_output_fields:
                    additional_attributes.append(source_feature[field.name()])
                try:
                    found_feature = uldk_response_to_qgs_feature(uldk_response_row, additional_attributes)
                    geometry_wkt = found_feature.geometry().asWkt()
                except BadGeometryException:
                    raise BadGeometryException("Niepoprawna geometria")
                saved = False
                if geometry_wkt not in geometries:
                    saved = True
                    found_features.append(found_feature)
                    self.layer_found.dataProvider().addFeature(found_feature)
                    geometries.append(geometry_wkt)
                self.progressed.emit(True, 0, saved)
            except Exception as e:
                not_found_feature = self.__make_not_found_feature(source_feature.geometry(), e)
                self.layer_not_found.dataProvider().addFeature(not_found_feature)
                self.progressed.emit(False, 0, False)
            
        self.__commit()
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



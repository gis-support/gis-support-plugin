from PyQt5.QtCore import QVariant
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsCoordinateTransformContext, QgsFeature, QgsField,
                       QgsFields, QgsGeometry, QgsProject, QgsVectorLayer, Qgis, QgsRectangle)
from qgis.utils import iface
from typing import Optional, Tuple, List

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



class ResultCollector:

    SOURCE_CRS = QgsCoordinateReferenceSystem.fromEpsgId(2180)

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
        def __init__(self, feature: QgsFeature, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.feature = feature

    class ResponseDataException(Exception):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

    @classmethod
    def default_layer_factory(cls,
            name: str = "Wyniki wyszukiwania ULDK",
            epsg: int = 2180,
            custom_properties: dict= {"ULDK":"plots_layer"},
            additional_fields: List[QgsField] = [],
            base_fields: List[QgsField] = PLOTS_LAYER_DEFAULT_FIELDS) -> QgsVectorLayer:

        fields = base_fields + additional_fields
        layer = QgsVectorLayer("Polygon?crs=EPSG:{}".format(epsg), name, "memory")
        layer.startEditing()
        for prop, value in custom_properties.items():
            layer.setCustomProperty(prop, value)
        layer.dataProvider().addAttributes(fields)
        layer.commitChanges()
        return layer

    @classmethod
    def uldk_response_to_qgs_feature(cls, response_row: str, additional_attributes: list = []) -> QgsFeature:
        def get_sheet(teryt):
            split = teryt.split(".")
            if len(split) == 4:
                return split[2]
            else:
                return

        try:
            geom_wkt, province, county, municipality, precinct, plot_id, teryt = \
                response_row.split("|")
        except ValueError:
            raise cls.ResponseDataException()

        sheet = get_sheet(teryt)

        ewkt = geom_wkt.split(";")
        if len(ewkt) == 2:
            geom_wkt = ewkt[1]

        feature = QgsFeature()
        fields = QgsFields()
        for field in PLOTS_LAYER_DEFAULT_FIELDS:
            fields.append(field)
        feature.setFields(fields)

        geometry = QgsGeometry.fromWkt(geom_wkt)
        feature.setGeometry(geometry)

        area = geometry.area()
        attributes = [province, county, municipality, precinct, sheet, plot_id, teryt, area]

        if additional_attributes:
            attributes += additional_attributes

        feature.setAttributes(attributes)

        if not geometry.isGeosValid():
            geometry = geometry.makeValid()
            if not geometry.isGeosValid():
                raise cls.BadGeometryException(feature)

        return feature

    @classmethod
    def _add_feature_with_session(cls, layer: QgsVectorLayer, feature_to_add: Optional[QgsFeature]) -> bool:
        """Logika bezpiecznej sesji edycyjnej"""
        if feature_to_add is None:
            return False

        was_editable = layer.isEditable()

        if was_editable and layer.isModified():
            iface.messageBar().pushMessage(
                "Wtyczka GIS SUPPORT - ULDK",
                "Przed kontynuowaniem musisz zapisać zmiany w warstwie.",
                level=Qgis.Warning)
            return False

        if not was_editable:
            layer.startEditing()

        success = layer.addFeature(feature_to_add)

        if success:
            return layer.commitChanges(stopEditing=not was_editable)

        return success

    @classmethod
    def _map_attributes_by_name(cls, target_layer: QgsVectorLayer, source_feature: QgsFeature) -> QgsFeature:
        """Mapowanie atrybutów po nazwach dla istniejącej warstwy"""
        new_feat = QgsFeature(target_layer.fields())

        # Sprawdzenie i porównaie układów
        geometry = source_feature.geometry()
        target_crs = target_layer.crs()

        # Transformacja jeśli są różne
        if cls.SOURCE_CRS != target_crs:
            geometry.transform(QgsCoordinateTransform(cls.SOURCE_CRS, target_crs, QgsProject.instance()))

        new_feat.setGeometry(geometry)

        target_fields = target_layer.fields()
        for target_name, source_name in cls.ATTRIBUTE_MAPPING.items():
            field_idx = target_fields.lookupField(target_name)
            if field_idx != -1:
                new_feat.setAttribute(field_idx, source_feature[source_name])

        return new_feat

class ResultCollectorSingle(ResultCollector):

    def __init__(self, parent, layer_factory=None):
        self.parent = parent
        self.canvas = parent.canvas
        self.layer_factory = layer_factory
        self.layer = None
        self._memory_layer = None
        if not layer_factory:
            self.layer_factory = lambda: self.default_layer_factory()

    def __create_layer(self):
        layer = self.layer_factory()
        layer.willBeDeleted.connect(self.__delete_layer)
        self._memory_layer = layer

    def __delete_layer(self):
        self._memory_layer = None
        if self.layer == self._memory_layer:
            self.layer = None

    def update(self, uldk_response: str) -> Optional[QgsFeature]:
        feature = self.uldk_response_to_qgs_feature(uldk_response)
        return self.update_with_feature(feature)

    def update_with_feature(self, feature: QgsFeature) -> Optional[QgsFeature]:
        dock = self.parent.dockwidget

        if dock.radioExistingLayer.isChecked():
            target_layer = dock.comboLayers.currentLayer()
            if not target_layer:
                iface.messageBar().pushMessage(
                    "Wtyczka GIS SUPPORT - ULDK",
                    "Nie wybrano warstwy docelowej",
                    level=Qgis.Critical)
                return

            self.layer = target_layer

            mapped_feature = self._map_attributes_by_name(target_layer, feature)
            if self._add_feature_with_session(target_layer, mapped_feature):
                target_layer.updateExtents()
                return mapped_feature
            return
        else:
            # Tryb warstwy tymczasowej
            if self._memory_layer is None:
                self.__create_layer()
                QgsProject.instance().addMapLayer(self._memory_layer)

            self.layer = self._memory_layer

            if self._add_feature_with_session(self._memory_layer, feature):
                self._memory_layer.updateExtents()
                return feature
            return feature

    def zoom_to_feature(self, feature: Optional[QgsFeature]) -> Optional[QgsRectangle]:
        if feature is None:
            return

        canvas_crs = self.canvas.mapSettings().destinationCrs()
        transformation = QgsCoordinateTransform(self.SOURCE_CRS, canvas_crs, QgsCoordinateTransformContext())
        target_bbox = transformation.transformBoundingBox(feature.geometry().boundingBox())
        self.canvas.setExtent(target_bbox)

        return target_bbox


class ResultCollectorMultiple(ResultCollector):

    def __init__(self, parent, target_layer):
        self.canvas = parent.canvas
        self.layer = target_layer


    def update(self, uldk_response_rows):
        self.layer.startEditing()
        for row in uldk_response_rows:
            feature = self.uldk_response_to_qgs_feature(row)
            self.layer.addFeature(feature)
        self.layer.commitChanges()
        self.layer.updateExtents()
        QgsProject.instance().addMapLayer(self.layer)

    def update_with_features(self, features):
        self.layer.startEditing()
        for feature in features:
            self.layer.addFeature(feature)
        self.layer.commitChanges()
        self.layer.updateExtents()
        QgsProject.instance().addMapLayer(self.layer)
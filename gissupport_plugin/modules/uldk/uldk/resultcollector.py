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
                return None

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

        if layer.isEditable():
            if layer.isModified():
                iface.messageBar().pushMessage(
                    "Wtyczka GIS SUPPORT - ULDK",
                    "Przed kontynuowaniem musisz zapisać zmiany w warstwie.",
                    level=Qgis.Warning)
                return False
            was_editable = True
        else:
            layer.startEditing()
            was_editable = False
        
        success = layer.addFeature(feature_to_add)

        if success:
            if not was_editable:
                layer.commitChanges()
            else:
                layer.commitChanges(stopEditing=False)
            return True
        
        return success
    
    @classmethod
    def _map_attributes_by_name(cls, target_layer: QgsVectorLayer, source_feature: QgsFeature) -> Tuple[QgsFeature, List[str]]:
        """Mapowanie atrybutów po nazwach dla istniejącej warstwy"""
        new_feat = QgsFeature(target_layer.fields())

        # Sprawdzenie i porównaie układów
        geometry = source_feature.geometry()
        source_crs = QgsCoordinateReferenceSystem.fromEpsgId(2180)
        target_crs = target_layer.crs()

        # Transformacja jeśli są różne
        if source_crs != target_crs:
            geometry.transform(QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance()))

        new_feat.setGeometry(geometry)

        mapping = {
            'wojewodztwo': 0, 'woj': 0,
            'powiat': 1,
            'gmina': 2,
            'obreb': 3,
            'arkusz': 4,
            'nr_dzialki': 5,
            'teryt': 6,
            'pow_m2': 7
        }
        
        found_indices = set()
        source_attrs = source_feature.attributes()

        for field in target_layer.fields():
            name_lower = field.name().lower()
            if name_lower in mapping:
                source_idx = mapping[name_lower]
                new_feat.setAttribute(field.name(), source_attrs[source_idx])
                found_indices.add(source_idx)
        
        missing = []
        for i in range(8):
            if i not in found_indices:
                for label, source_idx in mapping.items():
                    if source_idx == i:
                        missing.append(label)
                        break

        return new_feat, missing

class ResultCollectorSingle(ResultCollector):

    def __init__(self, parent, layer_factory=None):
        self.parent = parent
        self.canvas = parent.canvas
        self.layer_factory = layer_factory
        self.layer = None
        if not layer_factory:
            self.layer_factory = lambda: self.default_layer_factory()

    def __create_layer(self):
        layer = self.layer_factory()
        layer.willBeDeleted.connect(self.__delete_layer)
        self.layer = layer

    def __delete_layer(self):
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
                return None
            
            mapped_feature, missing = self._map_attributes_by_name(target_layer, feature)

            if missing:
                msg = f"Nie udało się zmapować pól: \
                    {', '.join(missing)}.  Popraw nazwy kolumn w tabeli. Nazwę poprawnych nazw znajdziesz w informacji."
                iface.messageBar().pushMessage("Wtyczka GIS SUPPORT - ULDK", msg, level=Qgis.Info, duration=10)

            if self._add_feature_with_session(target_layer, mapped_feature):
                target_layer.updateExtents()
                return mapped_feature
            return None
        else:
            if self.layer is None:
                self.__create_layer()
                QgsProject.instance().addMapLayer(self.layer)

            if self._add_feature_with_session(self.layer, feature):
                self.layer.updateExtents()
                return feature
            return feature

    def zoom_to_feature(self, feature: Optional[QgsFeature]) -> Optional[QgsRectangle]:
        if feature is None:
            return None
        
        crs_2180 = QgsCoordinateReferenceSystem.fromEpsgId(2180)
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        transformation = QgsCoordinateTransform(crs_2180, canvas_crs, QgsCoordinateTransformContext())
        target_bbox = transformation.transformBoundingBox(feature.geometry().boundingBox())
        self.canvas.setExtent(target_bbox)

        return target_bbox

    def __add_feature(self, feature: QgsFeature) -> Optional[QgsFeature]:
        
        self.layer.startEditing()
        self.layer.dataProvider().addFeature(feature)
        self.layer.commitChanges()

        return feature

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
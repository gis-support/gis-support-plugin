from PyQt5.QtCore import QVariant
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsCoordinateTransformContext, QgsFeature, QgsField,
                       QgsFields, QgsGeometry, QgsProject, QgsVectorLayer)

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



class ResultCollector:

    class BadGeometryException(Exception):
        def __init__(self, feature: QgsFeature, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.feature = feature

    @classmethod
    def default_layer_factory(cls, name = "Wyniki wyszukiwania ULDK",
            epsg = 2180, custom_properties = {"ULDK":"plots_layer"},
            additional_fields = [], base_fields = PLOTS_LAYER_DEFAULT_FIELDS ):
        fields = base_fields + additional_fields
        layer = QgsVectorLayer("Polygon?crs=EPSG:{}".format(epsg), name, "memory")
        layer.startEditing()
        for prop, value in custom_properties.items():
            layer.setCustomProperty(prop, value)
        layer.dataProvider().addAttributes(fields)
        layer.commitChanges()
        return layer

    @classmethod
    def uldk_response_to_qgs_feature(cls, response_row, additional_attributes=[]):
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
    
    def update(self, uldk_response):
        feature = self.uldk_response_to_qgs_feature(uldk_response)
        return self.update_with_feature(feature)
    
    def update_with_feature(self, feature):
        if self.layer is None:
            self.__create_layer()
            QgsProject.instance().addMapLayer(self.layer)

        self.__add_feature(feature)
        self.layer.updateExtents()

        return feature

    def zoom_to_feature(self, feature):
        crs_2180 = QgsCoordinateReferenceSystem.fromEpsgId(2180)
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        transformation = QgsCoordinateTransform(crs_2180, canvas_crs, QgsCoordinateTransformContext())
        target_bbox = transformation.transformBoundingBox(feature.geometry().boundingBox())
        self.canvas.setExtent(target_bbox)
        return target_bbox

    def __add_feature(self, feature):
        
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
            self.layer.dataProvider().addFeature(feature)
        self.layer.commitChanges()
        self.layer.updateExtents()
        QgsProject.instance().addMapLayer(self.layer)

    def update_with_features(self, features):
        self.layer.startEditing()
        for feature in features:
            self.layer.dataProvider().addFeature(feature)
        self.layer.commitChanges()
        self.layer.updateExtents()
        QgsProject.instance().addMapLayer(self.layer)

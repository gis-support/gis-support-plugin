import json
import os
from json import JSONDecodeError

from qgis.PyQt.QtCore import pyqtSignal, QVariant
from qgis.core import (QgsPointXY, QgsGeometry, QgsFeature, QgsProject, QgsJsonUtils,
                       QgsCoordinateReferenceSystem, QgsVectorLayer, QgsField, QgsTask)

from gissupport_plugin.modules.gis_box.layers.geojson import geojson2geom
from gissupport_plugin.tools.gisbox_connection import GISBOX_CONNECTION


class AutoDigitizationTask(QgsTask):
    message_group_name = "GIS Support - Automatyczna wektoryzacja"
    task_layer_id_updated = pyqtSignal(str)
    task_downloaded_data = pyqtSignal()
    task_completed = pyqtSignal()
    task_failed = pyqtSignal(str)

    def __init__(self, description: str, digitization_option: list, data: dict, layer_id: str, clip: str):
        super().__init__(description, QgsTask.Flag.CanCancel)
        self.digitization_option = digitization_option
        self.data = data
        self.layer_id = layer_id
        self.clip = clip

    def run(self):
        response = GISBOX_CONNECTION.post(
            f"/api/automatic_digitization/{self.digitization_option[0]}?trim={self.clip}",
            self.data,
            srid='2180',
            sync=True
        )
        try:
            data = response
        except JSONDecodeError:
            self.task_failed.emit("Błąd odczytu danych nadesłanych z API")
            return False

        if data.get("data"):
            crs = QgsCoordinateReferenceSystem.fromEpsgId(2180)

            if (self.layer_id is None) or ((layer := QgsProject.instance().mapLayer(self.layer_id)) is None):
                layer = QgsVectorLayer("MultiPolygon", self.digitization_option[1], "memory")
                self.layer_id = layer.id()
                self.task_layer_id_updated.emit(self.layer_id)

            layer.setCrs(crs)

            dp = layer.dataProvider()
            dp.addAttributes([QgsField("best_label", QVariant.String)])
            dp.addAttributes([QgsField("class", QVariant.String)])
            dp.addAttributes([QgsField("labels", QVariant.String)])
            dp.addAttributes([QgsField("type", QVariant.String)])
            layer.updateFields()

            for feature in data["data"]["features"]:
                geometry = geojson2geom(feature["geometry"])

                attributes = feature["properties"]
                output_feature = QgsFeature()
                output_feature.setGeometry(geometry)
                output_feature.setAttributes([
                    attributes["best_label"],
                    attributes["class"],
                    str(attributes["labels"]),
                    attributes["type"]
                ])

                dp.addFeature(output_feature)

            if self.layer_id not in QgsProject.instance().mapLayers().keys():
                layer.loadNamedStyle(os.path.join(os.path.dirname(__file__), 'style.qml'))
                QgsProject.instance().addMapLayer(layer)
            else:
                layer.reload()

        elif error_msg := data.get("error_message"):
            self.task_failed.emit(error_msg)
            return False

        else:
            self.task_failed.emit(None)
            return False

        self.task_completed.emit()
        return True

    def finished(self, result: bool):
        pass

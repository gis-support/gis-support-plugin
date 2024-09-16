import json
import os

from PyQt5.QtCore import pyqtSignal, QVariant
from qgis.core import (QgsPointXY, QgsGeometry, QgsFeature, QgsProject,
                       QgsCoordinateReferenceSystem, QgsVectorLayer, QgsField, QgsTask)

from gissupport_plugin.tools.gisbox_connection import GISBOX_CONNECTION
from gissupport_plugin.tools.requests import NetworkHandler


class AutoDigitizationTask(QgsTask):
    message_group_name = "GIS Support - Automatyczna wektoryzacja"
    task_layer_id_updated = pyqtSignal(str)
    task_downloaded_data = pyqtSignal()
    task_completed = pyqtSignal()
    task_failed = pyqtSignal()

    def __init__(self, description: str, digitization_option: list, data: dict, layer_id: str):
        super().__init__(description, QgsTask.CanCancel)
        self.digitization_option = digitization_option
        self.data = data
        self.layer_id = layer_id

    def run(self):
        handler = NetworkHandler()
        response = handler.post(
            GISBOX_CONNECTION.host + f"/api/automatic_digitization/{self.digitization_option[0]}",
            True,
            data=self.data,
            srid='2180'
        )
        data = json.loads(response.readAll().data().decode())

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
                multipolygon = []

                coordinates = feature["geometry"]["coordinates"]
                for polygon in coordinates:
                    polygon_ = []
                    for point in polygon:
                        polygon_.append(QgsPointXY(point[0], point[1]))
                    multipolygon.append(polygon_)

                geometry = QgsGeometry().fromMultiPolygonXY([multipolygon])

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

        else:
            self.task_failed.emit()
            return False

        self.task_completed.emit()
        return True

    def finished(self, result: bool):
        pass

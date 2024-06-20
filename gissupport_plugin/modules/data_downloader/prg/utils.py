from enum import Enum
import requests

from qgis.core import QgsGeometry, QgsFeature, QgsTask, QgsCoordinateReferenceSystem, QgsVectorLayer, QgsProject, \
    QgsMessageLog, Qgis
from PyQt5.QtCore import QCoreApplication

from gissupport_plugin.tools.requests import NetworkHandler


class EntityOption(Enum):
    GMINA = "Gmina"
    POWIAT = "Powiat"
    WOJEWODZTWO = "Wojewodztwo"
    BRAK = "Brak (dla całego kraju)"


class PRGDownloadTask(QgsTask):

    message_group_name = "GIS Support - PRG granice administracyjne"

    url = "https://uldk.gugik.gov.pl"

    search_types_by_options = {
        "Gmina": {
            "param": "GetCommuneById",
            "name": "commune"
        },
        "Powiat": {
           "param": "GetCountyById",
           "name": "county"
        },
        "Wojewodztwo": {
            "param": "GetVoivodeshipById",
            "name": "voivodeship"
        },
        "Brak": {
            "name": "",
            "param": ""
        }
    }

    def __init__(self, description: str, duration: int, layer: QgsVectorLayer, entity_option: str, entity_teryt: str):
        self.layer = layer
        self.search_type = self.search_types_by_options[entity_option]["param"]
        self.result_parameter_name = self.search_types_by_options[entity_option]["name"]
        self.entity_teryt = entity_teryt
        super().__init__(description, QgsTask.CanCancel)

    def run(self):
        parameters = self._get_parameters()
        
        handler = NetworkHandler()
        response = handler.get(self.url, params=parameters)

        response_content = response["data"]
        status = response_content[0]

        dp = self.layer.dataProvider()
        if status != "0":
            self.log_message(f"{self.url} - odpowiedź: {response_content}", level=Qgis.Critical)
            self.cancel()

        features = self.response_as_features(response_content)
        if not features:
            return False

        for feature in features:
            self.layer.dataProvider().addFeature(feature)

        self.log_message(f"{self.url} - pobrano", level=Qgis.Info)

        return True

    def finished(self, result: bool):
        pass

    def _get_parameters(self):
        result_params = ["geom_wkt", self.result_parameter_name, "teryt"]
        return {
            "request": self.search_type,
            "id": self.entity_teryt,
            "result": ",".join(result_params)
        }

    @staticmethod
    def response_as_features(content: str):
        result = []
        data = content[1:]
        data = data.split("\n")

        if content.endswith("\n"):
            data = data[:-1]

        for object_data in data:
            if not object_data:
                continue

            ewkt = object_data.split(";")[1]

            additional_attributes = object_data.split("|")
            entity_name = additional_attributes[1]
            teryt = additional_attributes[2]

            if len(ewkt) == 2:
                geom_wkt = ewkt[1]
            else:
                geom_wkt = ewkt

            geometry = QgsGeometry.fromWkt(geom_wkt)
            if not geometry.isGeosValid():
                geometry = geometry.buffer(0.0, 1)
                if not geometry.isGeosValid():
                    raise

            feature = QgsFeature()
            feature.setGeometry(geometry)
            feature.setAttributes([entity_name, teryt])

            result.append(feature)

        return result

    def log_message(self, message: str, level: Qgis.MessageLevel):
        QgsMessageLog.logMessage(message, self.message_group_name, level)

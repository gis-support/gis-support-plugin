import json
from io import BytesIO

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsMessageLog,
    QgsProject,
    QgsTask,
)
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.utils import iface

from gissupport_plugin.tools.requests import NetworkHandler


class PRGAddressDownloadTask(QgsTask):
    message_group_name = "GIS Support - Punkty adresowe PRG"
    progress_updated = pyqtSignal(float)
    download_finished = pyqtSignal(bool)
    task_failed = pyqtSignal(str)

    def __init__(self, description: str, teryt_p: str, filepath: str):
        self.teryt_p = teryt_p
        self.filepath = filepath
        self.url = f"https://integracja.gugik.gov.pl/PRG/pobierz.php?teryt={self.teryt_p}&adresy_pow"
        super().__init__(description, QgsTask.CanCancel)

    def run(self):
        handler = NetworkHandler()
        response = handler.get(self.url, True)

        if response.error() != 0:
            self.task_failed.emit(
                "Błąd pobierania danych. Sprawdź swoje połączenie z Internetem oraz czy usługa Geoportal.gov.pl działa.")
            return False

        total_size = int(response.header(QNetworkRequest.ContentLengthHeader)) or 0
        data = BytesIO(response.readAll().data())
        bytes_received = 0
        full_filepath = f"{self.filepath}/{self.teryt_p}_GML.zip"
        with open(full_filepath, 'wb') as file:
            for chunk in iter(lambda: data.read(1024), b''):
                file.write(chunk)
                bytes_received += len(chunk)
                if total_size > 0:
                    progress = (bytes_received / total_size) * 100
                    self.progress_updated.emit(progress)

        self.log_message(f"{full_filepath} - pobrano", level=Qgis.Info)
        self.download_finished.emit(True)

        return True

    def finished(self, result: bool):
        pass

    def log_message(self, message: str, level: Qgis.MessageLevel):
        QgsMessageLog.logMessage(message, self.message_group_name, level)

class PRGAddressDataBoxDownloadTask(QgsTask):
    download_finished = pyqtSignal(bool)
    downloaded_data = pyqtSignal(str)
    downloaded_details = pyqtSignal(str)

    def __init__(self, description: str, layer: str, geojson: QgsGeometry):
        self.layer = layer
        self.geojson = json.loads(geojson.asJson())
        self.geojson["crs"] = {"type": "name", "properties": {"name": "EPSG:2180"}}
        self.bbox = geojson.boundingBox()
        self.url = f"https://databox.gis.support/api/2.0/functions/GetFeaturesByGeoJSON/prg_punkty_adresowe"
        super().__init__(description, QgsTask.CanCancel)

    def run(self):
        handler = NetworkHandler()
        response = handler.post(self.url, data=self.geojson, databox=True)
        if details := response.get("details"):
            self.downloaded_details.emit(f"Przekroczono limit danych ({details.get('limit')}) z Data.Box. Próbowano pobrać {details.get('count')} obiektów.")
            self.download_finished.emit(True)
            return False
        elif error := response.get("error"):
            if msg := response.get("msg"):
                self.downloaded_details.emit(msg)
            else:
                self.downloaded_details.emit(f"Błąd pobierania danych z Data.Box.")
            self.download_finished.emit(True)
            return False

        response_data = response.get("data")
        features = json.loads(response_data)["features"]
        geojson_dict = {"type": "FeatureCollection", "features": features}

        self.downloaded_data.emit(json.dumps(geojson_dict))
        self.download_finished.emit(True)
        return True

def convert_multi_polygon_to_polygon(geometry: QgsGeometry):
    # rubber bandy zwracają multipoligony, konieczne jest rozbicie geometrii przed wysłaniem do api oze
    geometry.convertToSingleType()
    crs_src = iface.mapCanvas().mapSettings().destinationCrs()
    geometry = transform_geometry_to_2180(geometry, crs_src)
    return geometry

def transform_geometry_to_2180(geometry: QgsGeometry, crs_src: QgsCoordinateReferenceSystem):
    crs_dest = QgsCoordinateReferenceSystem().fromEpsgId(2180)
    transform = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
    geometry.transform(transform)
    return geometry
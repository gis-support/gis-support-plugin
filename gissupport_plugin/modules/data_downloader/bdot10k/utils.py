from io import BytesIO
import json

from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.core import QgsTask, QgsMessageLog, Qgis, QgsWkbTypes, QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject, QgsGeometry
from gissupport_plugin.tools.requests import NetworkHandler
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.utils import iface


class BDOT10kDownloadTask(QgsTask):

    message_group_name = "GIS Support - BDOT10k Baza Danych Obiektów Topograficznych"
    progress_updated = pyqtSignal(float)
    download_finished = pyqtSignal(bool)
    task_failed = pyqtSignal(str)

    def __init__(self, description: str, teryt_woj: str, teryt_pow: str, filepath: str):
        self.teryt_woj = teryt_woj
        self.teryt_pow = teryt_pow
        self.filepath = filepath
        self.url = f"https://opendata.geoportal.gov.pl/bdot10k/schemat2021/{self.teryt_woj}/{self.teryt_pow}_GML.zip"
        super().__init__(description, QgsTask.Flag.CanCancel)

    def run(self) -> bool:
        handler = NetworkHandler()
        response = handler.get(self.url, True)

        if response.error() != 0:
            self.task_failed.emit("Błąd pobierania danych. Sprawdź swoje połączenie z Internetem oraz czy usługa Geoportal.gov.pl działa.")
            return False

        total_size = int(response.header(QNetworkRequest.KnownHeaders.ContentLengthHeader)) or 0
        data = BytesIO(response.readAll().data())
        bytes_received = 0
        full_filepath = f"{self.filepath}/{self.teryt_pow}_GML.zip"
        with open(full_filepath, 'wb') as file:
            for chunk in iter(lambda: data.read(1024), b''):
                file.write(chunk)
                bytes_received += len(chunk)
                if total_size > 0:
                    progress = (bytes_received / total_size) * 100
                    self.progress_updated.emit(progress)

        self.log_message(f"{full_filepath} - pobrano", level=Qgis.MessageLevel.Info)
        self.download_finished.emit(True)

        return True

    def finished(self, result: bool):
        pass

    def log_message(self, message: str, level: Qgis.MessageLevel) -> None:
        QgsMessageLog.logMessage(message, self.message_group_name, level)

class BDOT10kDataBoxDownloadTask(QgsTask):
    download_finished = pyqtSignal(bool)
    downloaded_data = pyqtSignal(str)
    downloaded_details = pyqtSignal(str)

    def __init__(self, description: str, layer: str, geojson: QgsGeometry):
        super().__init__(description, QgsTask.Flag.CanCancel)
        self.layer = layer

        #Zabezpieczenie przed pustą geometrią
        try:
            json_str = geojson.asJson()
            if json_str == 'null' or json_str is None:
                # Jeśli asJson zwraca 'null', geometry jest puste/błędne
                self.geojson = None
            else:
                self.geojson = json.loads(json_str)
        except Exception:
            self.geojson = None

        if self.geojson is None:
            QgsMessageLog.logMessage("Przekazano nieprawidłową geometrię do zadania pobierania!", "GIS Support", Qgis.MessageLevel.Warning)
            return

        self.geojson["crs"] = {"type": "name", "properties": {"name": "EPSG:2180"}}
        self.url = f"https://api-oze.gisbox.pl/layers/{self.layer}?output_srid=2180&promote_to_multi=false"

    def run(self) -> bool:
        # Sprawdzamy czy init przeszedł poprawnie
        if not hasattr(self, 'geojson') or self.geojson is None:
            return False

        handler = NetworkHandler()
        response = handler.post(self.url, data=self.geojson, databox=True)
        if details := response.get("details"):
            self.downloaded_details.emit(f"Przekroczono limit danych ({details.get('limit')}) z Data.Box. Próbowano pobrać {details.get('count')} obiektów.")
            self.download_finished.emit(True)
            return False

        self.downloaded_data.emit(response.get("data"))
        self.download_finished.emit(True)
        return True

class BDOT10kClassDownloadTask(QgsTask):
    message_group_name = "GIS Support - BDOT10k Baza Danych Obiektów Topograficznych"
    progress_updated = pyqtSignal(float)
    download_finished = pyqtSignal(bool)

    def __init__(self, description: str, bdot_class: str, filepath: str):
        self.bdot_class = bdot_class
        self.filepath = filepath
        self.url = f"https://s3.gis.support/public/bdot10k/{self.bdot_class}.gpkg"
        super().__init__(description, QgsTask.Flag.CanCancel)

    def run(self) -> bool:
        handler = NetworkHandler()
        handler.downloadProgress.connect( lambda value: self.setProgress(value) )
        response = handler.get(self.url, reply_only=True)
        total_size = int(response.header(QNetworkRequest.KnownHeaders.ContentLengthHeader)) or 0
        bytes_received = 0
        full_filepath = f"{self.filepath}/{self.bdot_class}.gpkg"
        with open(full_filepath, 'wb') as file:
            while (chunk:=response.read(1024)):
                file.write(chunk)
                bytes_received += len(chunk)
                if total_size > 0:
                    progress = (bytes_received / total_size) * 100
                    self.progress_updated.emit(progress)

        self.log_message(f"{full_filepath} - pobrano", level=Qgis.MessageLevel.Info)
        self.download_finished.emit(True)

        return True

    def log_message(self, message: str, level: Qgis.MessageLevel) -> None:
        QgsMessageLog.logMessage(message, self.message_group_name, level)

def get_databox_layers():
    handler = NetworkHandler()
    url = 'https://api-oze.gisbox.pl/layers'
    response = handler.get(url)
    if response.get("data") is None:
        raise DataboxResponseException("Brak odpowiedzi")
    layer_list = json.loads(response.get("data"))
    layer_list = {v: k for k, v in layer_list.items()}
    return layer_list

def check_geoportal_connection() -> bool:
    handler = NetworkHandler()
    url = "https://opendata.geoportal.gov.pl"
    response = handler.get(url, True)
    if response.error() != 0:
        raise GeoportalResponseException("Brak odpowiedzi")
    return True

def convert_multi_polygon_to_polygon(geometry: QgsGeometry) -> QgsGeometry:
    # rubber bandy zwracają multipoligony, konieczne jest rozbicie geometrii przed wysłaniem do api oze
    geometry.convertToSingleType()
    crs_src = iface.mapCanvas().mapSettings().destinationCrs()
    geometry = transform_geometry_to_2180(geometry, crs_src)
    return geometry

def transform_geometry_to_2180(geometry: QgsGeometry, crs_src: QgsCoordinateReferenceSystem) -> QgsGeometry:
    crs_dest = QgsCoordinateReferenceSystem().fromEpsgId(2180)
    transform = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
    geometry.transform(transform)
    return geometry

class DrawPolygon(QgsMapTool):
    """Narzędzie do rysowania poligonu"""
    selectionDone = pyqtSignal(QgsGeometry)
    move = pyqtSignal()

    def __init__(self, parent):
        canvas = iface.mapCanvas()
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas
        self.parent = parent
        self.rb = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
        self.rb.setColor(QColor(255, 0, 0, 100))
        self.rb.setFillColor(QColor(255, 0, 0, 33))
        self.rb.setWidth = 10
        self.drawing = False

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reset()

    def canvasPressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self.drawing is False:
                self.rb.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
                self.drawing = True
            self.rb.addPoint(self.toMapCoordinates(e.pos()))
        elif e.button() == Qt.MouseButton.RightButton and self.drawing:
            if self.rb.numberOfVertices() > 2:
                self.rb.removeLastPoint(0)
                self.drawing = False
                geometry = self.rb.asGeometry()
                self.rb.setToGeometry(geometry, None)
                self.selectionDone.emit(geometry)
            else:
                self.reset()

    def canvasMoveEvent(self, e):
        if self.rb.numberOfVertices() > 0  and self.drawing:
            self.rb.removeLastPoint(0)
            self.rb.addPoint(self.toMapCoordinates(e.pos()))
        self.move.emit()

    def reset(self):
        self.drawing = False
        self.rb.reset(QgsWkbTypes.GeometryType.PolygonGeometry)

    def deactivate(self):
        self.rb.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
        self.drawing = False
        QgsMapTool.deactivate(self)
        self.canvas.unsetMapTool(self)

class DataboxResponseException(Exception):
    pass

class GeoportalResponseException(Exception):
    pass

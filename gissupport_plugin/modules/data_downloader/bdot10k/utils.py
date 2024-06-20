from io import BytesIO
import requests

from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsTask, QgsMessageLog, Qgis
from gissupport_plugin.tools.requests import NetworkHandler
from PyQt5.QtNetwork import QNetworkRequest

class BDOT10kDownloadTask(QgsTask):

    message_group_name = "GIS Support - BDOT10k Baza Danych Obiektów Topograficznych"
    progress_updated = pyqtSignal(float)
    download_finished = pyqtSignal(bool)

    def __init__(self, description: str, teryt_woj: str, teryt_pow: str, filepath: str):
        self.teryt_woj = teryt_woj
        self.teryt_pow = teryt_pow
        self.filepath = filepath
        self.url = f"https://opendata.geoportal.gov.pl/bdot10k/schemat2021/{self.teryt_woj}/{self.teryt_pow}_GML.zip"
        super().__init__(description, QgsTask.CanCancel)

    def run(self):
        handler = NetworkHandler()
        response = handler.get(self.url, True)

        total_size = int(response.header(QNetworkRequest.ContentLengthHeader)) or 0
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
                    
        self.log_message(f"{full_filepath} - pobrano", level=Qgis.Info)
        self.download_finished.emit(True)

        return True

    def finished(self, result: bool):
        pass

    def log_message(self, message: str, level: Qgis.MessageLevel):
        QgsMessageLog.logMessage(message, self.message_group_name, level)

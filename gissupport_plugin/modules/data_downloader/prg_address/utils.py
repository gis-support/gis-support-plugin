from io import BytesIO

from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsTask, QgsMessageLog, Qgis

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


import os
from io import BytesIO

from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsTask, QgsMessageLog, Qgis, QgsRectangle
from gissupport_plugin.tools.requests import NetworkHandler


class NMPTdownloadTask(QgsTask):
    
    message_group_name = "GIS Support - Numeryczny Model (Pokrycia) Terenu"
    download_filepath = pyqtSignal(list)

    def __init__(
            self,
            description: str,
            data_format: str,
            datum_format: str,
            bbox: QgsRectangle,
            filepath: str):

        self.data_format = data_format
        self.datum_format = datum_format
        self.file_format = '.tiff' if data_format == 'DigitalTerrainModelFormatTIFF' else '.asc'
        self.bbox = bbox
        self.filepath = filepath
        self.url = self.prepare_url()
        super().__init__(description, QgsTask.CanCancel)


    def prepare_url(self):
        if self.data_format == 'DigitalSurfaceModel':
            datum_prefix = 'DSM'
            datum_letter = 'P'
            res = '0.5'
        else:
            datum_prefix = 'DTM'
            datum_letter = ''
            res = '1'

        if self.data_format == 'DigitalTerrainModelFormatTIFF':
            file_format = 'tiff'
            datum_format_suffix = '_TIFF'
        else:
            file_format = 'x-aaigrid'
            datum_format_suffix = ''

        url = (
            "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NM"
            f"{datum_letter}T/GRID1/WCS/{self.data_format}"
            "?service=wcs&request=GetCoverage&version=1.0.0&coverage="
            f"{datum_prefix}_PL-{self.datum_format}-NH"
            f"{datum_format_suffix}&format=image%2F{file_format}"
            f"&bbox={self.bbox.xMinimum()}%2C{self.bbox.yMinimum()}"
            f"%2C{self.bbox.xMaximum()}%2C{self.bbox.yMaximum()}"
            f"&resx={res}&resy={res}&crs=EPSG%3A2180"
        )

        return url

    def run(self):
        handler = NetworkHandler()
        response = handler.get(self.url, True)

        data = BytesIO(response.readAll().data())
        base_filepath = os.path.join(self.filepath, f"{self.data_format}{self.file_format}")

        full_filepath = base_filepath
        counter = 1
        while os.path.exists(full_filepath):
            name, ext = os.path.splitext(base_filepath)
            full_filepath = f"{name}_{counter}{ext}"
            counter += 1

        with open(full_filepath, 'wb') as file:
            for chunk in iter(lambda: data.read(1024), b''):
                file.write(chunk)

        self.log_message(f"{full_filepath} - pobrano", level=Qgis.Info)
        self.download_filepath.emit([full_filepath, self.data_format])

        return True

    def finished(self, result: bool):
        pass

    def log_message(self, message: str, level: Qgis.MessageLevel):
        QgsMessageLog.logMessage(message, self.message_group_name, level)

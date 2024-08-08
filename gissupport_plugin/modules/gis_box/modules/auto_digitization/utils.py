import os

from PyQt5.QtCore import pyqtSignal
from qgis.core import (
    QgsTask
)


class AutoDigitizationTask(QgsTask):
    message_group_name = "GIS Support - Automatyczna wektoryzacja"
    completed = pyqtSignal(dict)

    def __init__(self, description: str):
        super().__init__(description, QgsTask.CanCancel)

    def run(self):
        return True

    def finished(self, result: bool):
        pass

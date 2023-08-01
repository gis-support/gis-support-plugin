import configparser
import os

from qgis.core import QgsMessageLog, Qgis
from qgis.utils import iface
from typing import Any

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), '..', 'metadata.txt'))

PLUGIN_NAME = config['general']['name']


class Logger:
    @staticmethod
    def log( message: Any, level: Qgis.MessageLevel = Qgis.Info) -> None:
        """ Skrót do logowania informacji w konsoli QGIS """
        QgsMessageLog.logMessage(str(message), f'{PLUGIN_NAME} Log', level)

    @staticmethod
    def message(message: Any, title: str = PLUGIN_NAME, level: Qgis.MessageLevel = Qgis.Info, duration: int = 0) -> None:
        """ Skrót do komunikacji z użytkownikiem """
        iface.messageBar().pushMessage(title, str(message), level, duration)

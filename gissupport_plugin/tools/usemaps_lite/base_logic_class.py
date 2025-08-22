from PyQt5 import QtWidgets
from qgis.utils import iface

from gissupport_plugin.tools.usemaps_lite.requests import API_CLIENT
from gissupport_plugin.tools.usemaps_lite.event_handler import EVENT_HANDLER

class BaseLogicClass:
    """
    Bazowa klasa dla pozostałych klas obsługujących logikę.
    Kazda klasa posiada dostęp do głównego dockwidgetu i klienta API.
    """

    def __init__(self, dockwidget: QtWidgets.QDockWidget):

        self.dockwidget = dockwidget
        self.api = API_CLIENT
        self.event_handler = EVENT_HANDLER

    def show_error_message(self, message: str) -> None:
        """
        Wyświetla dymek z błędem.
        """

        iface.messageBar().pushCritical("GIS.Box Lite", message)

    def show_success_message(self, message: str) -> None:
        """
        Wyświetla dymek z sukcesem.
        """

        iface.messageBar().pushSuccess("GIS.Box Lite", message)
    
    def show_info_message(self, message: str) -> None:
        """
        Wyświetla dymek z info.
        """

        iface.messageBar().pushInfo("GIS.Box Lite", message)

import os

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'mapster_dockwidget.ui'))


class MapsterDockwidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super(MapsterDockwidget, self).__init__(parent)
        self.setupUi(self)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

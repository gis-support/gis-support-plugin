import os

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal

from qgis.utils import iface
from qgis.PyQt.QtCore import Qt


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'wmts_dockwidget.ui'))


class WMTSDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super(WMTSDockWidget, self).__init__(parent)
        self.setupUi(self)

        iface.addDockWidget(Qt.RightDockWidgetArea, self)
        self.hide()

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()


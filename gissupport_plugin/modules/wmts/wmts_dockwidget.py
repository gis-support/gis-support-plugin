import os

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.utils import iface

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


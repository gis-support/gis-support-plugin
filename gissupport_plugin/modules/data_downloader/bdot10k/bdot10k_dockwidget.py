import os

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
from qgis._core import QgsMapLayerProxyModel

from gissupport_plugin.tools.widgets.gs_select_area import GsSelectArea

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'bdot10k_dockwidget.ui'))


class BDOT10kDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super(BDOT10kDockWidget, self).__init__(parent)
        self.setupUi(self)

        self.selectAreaWidget = GsSelectArea(select_layer_types=[QgsMapLayerProxyModel.PolygonLayer])
        self.widgetLayout.addWidget(self.selectAreaWidget)

        self.setWindowTitle("BDOT10k - Baza Danych Obiektów Topograficznych")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

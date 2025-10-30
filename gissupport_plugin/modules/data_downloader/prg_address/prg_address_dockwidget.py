import os

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
from qgis.core import QgsMapLayerProxyModel

from gissupport_plugin.tools.widgets.gs_select_area import GsSelectArea

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'prg_address_dockwidget.ui'))


class PRGAddressDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super(PRGAddressDockWidget, self).__init__(parent)
        self.setupUi(self)

        self.gsSelectAreaWidget = GsSelectArea(select_layer_types=[QgsMapLayerProxyModel.PolygonLayer])
        self.widgetLayout.addWidget(self.gsSelectAreaWidget)

        self.setWindowTitle("PRG - dane adresowe")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

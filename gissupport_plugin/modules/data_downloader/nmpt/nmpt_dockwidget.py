import os

from qgis._core import QgsMapLayerProxyModel
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal

from gissupport_plugin.tools.widgets.gs_select_area import GsSelectArea

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'nmpt_dockwidget.ui'))


class NMPTdockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super(NMPTdockWidget, self).__init__(parent)
        self.setupUi(self)

        self.selectAreaWidget = GsSelectArea(select_layer_types=[QgsMapLayerProxyModel.PolygonLayer])
        self.widgetLayout.addWidget(self.selectAreaWidget)

        self.setWindowTitle("NM(P)T - Numeryczny Model (Pokrycia) Terenu")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

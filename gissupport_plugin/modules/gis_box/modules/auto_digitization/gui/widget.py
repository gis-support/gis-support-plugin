# -*- coding: utf-8 -*-
import json
import os

from PyQt5.QtGui import QColor
from qgis.PyQt import QtGui, uic
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsCoordinateTransform, QgsCoordinateTransformContext
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsProject
from qgis.core import QgsGeometry
from qgis.core import QgsWkbTypes
from qgis.gui import QgsRubberBand
from qgis.utils import iface

from gissupport_plugin.modules.gis_box.modules.auto_digitization.tools import SelectRectangleTool
from gissupport_plugin.tools.gisbox_connection import GISBOX_CONNECTION

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'widget.ui'))


class AutoDigitizationWidget(QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(AutoDigitizationWidget, self).__init__(parent)
        self.setupUi(self)

        self.lbWarning.setVisible(False)
        self.areaWidget.setHidden(True)
        self.btnExecute.setEnabled(False)

        self.registerTools()
        self.menageSignals()

        self.area = 0
        self.geom = None
        self.options = None

        self.getOptions()

    def menageSignals(self):
        """ Zarządzanie sygnałami """
        # self.btnSelectArea.clicked.connect(self.selectArea)
        self.btnExecute.clicked.connect(self.execute)
        self.selectRectangleTool.rectangleChanged.connect(self.areaChanged)
        self.selectRectangleTool.rectangleEnded.connect(self.areaEnded)
        self.areaReset.clicked.connect(self.areaInfoReset)

    def registerTools(self):
        """ Zarejestrowanie narzędzi jak narzędzi mapy QGIS """
        self.selectRectangleTool = SelectRectangleTool(self)
        self.selectRectangleTool.setButton(self.btnSelectArea)
        self.btnSelectArea.clicked.connect(lambda: self.activateTool(self.selectRectangleTool))


    def activateTool(self, tool):
        """ Zmiana aktywnego narzędzia mapy """
        iface.mapCanvas().setMapTool(tool)


    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def showInfo(self):
        self.infoDialog.show()

    def getOptions(self):
        self.options = GISBOX_CONNECTION.get(
            f"/api/automatic_digitization", True
        )
        self.digitizationOptions.clear()
        self.digitizationOptions.addItems(self.options["data"].values())


    def areaChanged(self, area: float = 0):
        self.area = area
        if area > 100:
            self.lbWarning.setVisible(True)
            self.btnExecute.setEnabled(False)
        else:
            self.lbWarning.setVisible(False)
            self.btnExecute.setEnabled(True)

    def areaEnded(self, area: float = 0, geom: QgsGeometry = None):
        self.area = area
        self.geom = geom
        self.areaWidget.setHidden(True)
        self.areaInfo.setText("Powierzchnia: {:.2f} ha".format(area))
        self.areaWidget.setHidden(False)

    def areaInfoReset(self):
        self.lbWarning.setVisible(False)
        self.areaWidget.setHidden(True)
        self.btnExecute.setEnabled(False)

        self.area = 0

        self.areaInfo.setText("Powierzchnia: 0 ha")
        self.selectRectangleTool.reset()

    def execute(self):
        current_crs = QgsProject.instance().crs()
        crs_2180 = QgsCoordinateReferenceSystem.fromEpsgId(2180)
        if current_crs != crs_2180:
            transformation = QgsCoordinateTransform(current_crs, crs_2180, QgsProject.instance())
            self.geom.transform(transformation)

        self.geom.convertToSingleType()
        geojson = json.loads(self.geom.asJson())

        data = {
            "data": {
                "geometry": {
                    "coordinates": geojson["coordinates"],
                    "type": geojson["type"],
                    "crs": {
                        "properties": {
                            "name": "EPSG:2180"
                        },
                        "type": "name"
                    }
                }
            }
        }

        # GISBOX_CONNECTION.get(
        #     f"/api/automatic_digitization/classification_contours?background=false",
        #     False, callback=self.createShapefile
        # )

        GISBOX_CONNECTION.post(
            "/api/automatic_digitization/classification_contours",
            data, srid=2180, callback=self.createShapefile
        )

    def createShapefile(self, data):
        print("done")

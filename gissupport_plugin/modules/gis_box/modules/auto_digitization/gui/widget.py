# -*- coding: utf-8 -*-
import json
import os

from PyQt5.QtCore import QVariant
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import (Qgis, QgsPointXY, QgsVectorLayer, QgsField, QgsFeature, QgsCoordinateTransform,
                       QgsCoordinateReferenceSystem, QgsProject, QgsGeometry
                       )
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
        self.layer = None
        self.layer_is_added = False

        self.getOptions()

    def menageSignals(self):
        """ Zarządzanie sygnałami """
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
        iface.messageBar().pushMessage(
            "Automatyczna wektoryzacja", "Rozpoczęto automatyczną wektoryzację dla zadanego obszaru.", level=Qgis.Info)
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

        options = self.options["data"]
        current_text = self.digitizationOptions.currentText()
        current_option = list(options.keys())[list(options.values()).index(current_text)]

        GISBOX_CONNECTION.post(
            f"/api/automatic_digitization/{current_option}?background=false",
            data, srid='2180', callback=self.createShapefile
        )

    def createShapefile(self, data):
        if data.get("data"):
            iface.messageBar().pushMessage(
                "Automatyczna wektoryzacja", "Trwa zapisywanie danych do warstwy tymczasowej.", level=Qgis.Info)
            crs = QgsCoordinateReferenceSystem.fromEpsgId(2180)

            if self.layer is None:
                self.layer = QgsVectorLayer("MultiPolygon", self.digitizationOptions.currentText(), "memory")

            self.layer.setCrs(crs)

            dp = self.layer.dataProvider()
            dp.addAttributes([QgsField("best_label", QVariant.String)])
            dp.addAttributes([QgsField("class", QVariant.String)])
            dp.addAttributes([QgsField("labels", QVariant.String)])
            dp.addAttributes([QgsField("type", QVariant.String)])
            self.layer.updateFields()

            for feature in data["data"]["features"]:
                multipolygon = []

                coordinates = feature["geometry"]["coordinates"]
                for part in coordinates:
                    part_ = []
                    for polygon in part:
                        polygon_ = []
                        for point in polygon:
                            polygon_.append(QgsPointXY(point[0], point[1]))
                        part_.append(polygon_)
                    multipolygon.append(part_)

                geometry = QgsGeometry().fromMultiPolygonXY(multipolygon)

                attributes = feature["properties"]
                output_feature = QgsFeature()
                output_feature.setGeometry(geometry)
                output_feature.setAttributes([
                    attributes["best_label"],
                    attributes["class"],
                    str(attributes["labels"]),
                    attributes["type"]
                ])

                dp.addFeature(output_feature)

            if not self.layer_is_added:
                QgsProject.instance().addMapLayer(self.layer)
                self.layer_is_added = True
            else:
                self.layer.reload()

            iface.messageBar().pushMessage(
                "Automatyczna wektoryzacja", "Pomyślnie zapisano dane do warstwy tymczasowej.", level=Qgis.Success)

        else:
            iface.messageBar().pushMessage(
                "Automatyczna wektoryzacja", "Zapisanie danych do warstwy tymczasowej nie powiodło się.", level=Qgis.Critical)

# -*- coding: utf-8 -*-
import json
import os

from PyQt5.QtGui import QCursor
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import (Qgis, QgsCoordinateTransform,
                       QgsCoordinateReferenceSystem, QgsProject, QgsGeometry, QgsApplication,
                       QgsMapLayerProxyModel
                       )
from qgis.utils import iface

from gissupport_plugin.modules.gis_box.modules.auto_digitization.utils import AutoDigitizationTask
from gissupport_plugin.tools.gisbox_connection import GISBOX_CONNECTION
from gissupport_plugin.tools.widgets.gs_select_area import GsSelectArea

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

        self.selectAreaWidget = GsSelectArea(select_layer_types=[QgsMapLayerProxyModel.PolygonLayer])

        self.registerTools()
        self.menageSignals()

        self.widgetLayout.addWidget(self.selectAreaWidget)

        self.task = None
        self.area = 0
        self.geom = None
        self.options = None
        self.layer_id = None
        self.projected = False


    def menageSignals(self):
        """ Zarządzanie sygnałami """
        self.btnExecute.clicked.connect(self.execute)
        self.select_features_rectangle_tool.geometryChanged.connect(self.areaChanged)
        self.select_features_rectangle_tool.geometryEnded.connect(self.areaEnded)
        self.select_features_freehand_tool.geometryChanged.connect(self.areaChanged)
        self.select_features_freehand_tool.geometryEnded.connect(self.areaEnded)
        self.select_features_tool.geometryChanged.connect(self.areaChanged)
        self.select_features_tool.geometryEnded.connect(self.areaEnded)
        self.areaReset.clicked.connect(self.areaInfoReset)

        self.selectAreaWidget.methodChanged.connect(self.on_select_method_changed)
        self.selectAreaWidget.selectLayerCb.layerChanged.connect(self.on_layer_changed)

    def registerTools(self):
        """ Zarejestrowanie narzędzi jak narzędzi mapy QGIS """
        self.select_features_rectangle_tool = self.selectAreaWidget.select_features_rectangle_tool
        self.select_features_freehand_tool = self.selectAreaWidget.select_features_freehand_tool
        self.select_features_tool = self.selectAreaWidget.select_features_tool

    def activateTool(self, tool):
        """ Zmiana aktywnego narzędzia mapy """
        self.area = 0
        self.geom = None
        iface.mapCanvas().setMapTool(tool)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        self.selectAreaWidget.closeWidget()
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
        elif area <= 0:
            self.lbWarning.setVisible(False)
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

        if self.selectAreaWidget.tool == self.select_features_tool:
            if self.area > 100:
                self.btnExecute.setEnabled(False)
            elif self.area <= 0:
                self.btnExecute.setEnabled(False)
            else:
                self.btnExecute.setEnabled(True)

    def areaInfoReset(self):
        self.lbWarning.setVisible(False)
        self.areaWidget.setHidden(True)
        self.btnExecute.setEnabled(False)

        self.area = 0

        self.areaInfo.setText("Powierzchnia: 0 ha")
        self.select_features_rectangle_tool.reset_geometry()
        self.select_features_freehand_tool.reset_geometry()
        self.select_features_tool.reset_geometry()

    def execute(self):
        iface.messageBar().pushMessage(
            "Automatyczna wektoryzacja", "Rozpoczęto automatyczną wektoryzację dla zadanego obszaru.", level=Qgis.Info)

        options = self.options["data"]
        current_text = self.digitizationOptions.currentText()
        current_option = list(options.keys())[list(options.values()).index(current_text)]

        digitization_option = (current_option, current_text)

        if not self.projected:
            current_crs = QgsProject.instance().crs()
            crs_2180 = QgsCoordinateReferenceSystem.fromEpsgId(2180)
            if current_crs != crs_2180:
                transformation = QgsCoordinateTransform(current_crs, crs_2180, QgsProject.instance())
                self.geom.transform(transformation)

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

        clip = 'true' if self.clipResultCheckBox.isChecked() is True else 'false'

        self.task = AutoDigitizationTask(
            "Automatyczna wektoryzacja", digitization_option, data, self.layer_id, clip
        )
        self.task.task_layer_id_updated.connect(self.task_layer_id_updated)
        self.task.task_downloaded_data.connect(self.task_downloaded_data)
        self.task.task_completed.connect(self.task_completed)
        self.task.task_failed.connect(self.task_failed)

        manager = QgsApplication.taskManager()
        manager.addTask(self.task)

        self.select_features_tool.deactivate()
        self.select_features_freehand_tool.deactivate()
        self.select_features_rectangle_tool.deactivate()

    def task_downloaded_data(self):
        iface.messageBar().pushMessage(
            "Automatyczna wektoryzacja", "Trwa zapisywanie danych do warstwy tymczasowej.", level=Qgis.Info)

    def task_completed(self):
        iface.messageBar().pushMessage(
                "Automatyczna wektoryzacja", "Pomyślnie zapisano dane do warstwy tymczasowej.", level=Qgis.Success)
        self.task = None
        self.select_features_rectangle_tool.reset_geometry()
        self.select_features_freehand_tool.reset_geometry()
        self.select_features_tool.reset_geometry()

    def task_failed(self, desc: str):
        if desc:
            message_description = desc
        else:
            message_description = "Zapisanie danych do warstwy tymczasowej nie powiodło się."
        iface.messageBar().pushMessage(
            "Automatyczna wektoryzacja", message_description,
            level=Qgis.Critical)
        self.task = None
        self.select_features_rectangle_tool.reset_geometry()
        self.select_features_freehand_tool.reset_geometry()
        self.select_features_tool.reset_geometry()

    def task_layer_id_updated(self, layer_id: str):
        self.layer_id = layer_id

    def on_select_method_changed(self):
        self.areaInfoReset()
        if self.selectAreaWidget.tool == self.select_features_tool:
            self.select_features_tool.activate()
            self.selectAreaWidget.selectLayerFeatsCb.stateChanged.connect(self.on_change_checkbox_state)

    def on_layer_changed(self):
        if self.selectAreaWidget.tool == self.select_features_tool:
            self.selectAreaWidget.selectLayerCb.currentLayer().selectionChanged.connect(self.on_selection_changed)
            self.select_features_tool.activate()

    def on_selection_changed(self):
        if self.selectAreaWidget.tool == self.select_features_tool:
            self.select_features_tool.activate()
            
    def on_change_checkbox_state(self):
        if self.selectAreaWidget.tool == self.select_features_tool:
            self.select_features_tool.activate()

    def select_features(self):
        iface.mapCanvas().setMapTool(self.select_features_tool)
        self.projected = True

    def select_features_rectangle(self):
        iface.mapCanvas().setMapTool(self.select_features_rectangle_tool)
        self.projected = False

    def select_features_freehand(self):
        iface.mapCanvas().setMapTool(self.select_features_freehand_tool)
        self.projected = False
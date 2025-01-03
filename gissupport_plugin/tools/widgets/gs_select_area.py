# -*- coding: utf-8 -*-

import os

from PyQt5.QtWidgets import QWidget
from qgis.core import QgsMapLayerProxyModel
from qgis.PyQt import uic
from qgis.utils import iface

from gissupport_plugin.modules.gis_box.modules.auto_digitization.tools import (
    SelectFeaturesTool, SelectRectangleTool, SelectFreehandTool)

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'gs_select_area.ui'))

class GsSelectArea(QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        super(GsSelectArea, self).__init__(parent)
        self.setupUi(self)

        self.tool = None

        self.selectLayerFeatsCb.setEnabled(False)
        self.selectLayerLabel.setEnabled(False)
        self.selectLayerCb.setEnabled(False)
        self.selectLayerCb.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        self.selectMethodCb.currentIndexChanged.connect(self.on_method_changed)
        self.selectAreaBtn.clicked.connect(self.on_select_area_button_pressed)

        self.select_features_tool = SelectFeaturesTool(self)
        self.select_features_rectangle_tool = SelectRectangleTool(self)
        self.select_features_freehand_tool = SelectFreehandTool(self)

    def on_method_changed(self, index):
        """Funkcja wywoływana przy zmianie metody wybierania obszaru"""
        selected_method = self.selectMethodCb.currentText()
        if self.selectMethodCb.currentIndex() == 2:
            self.tool = self.select_features_tool
            self.selectLayerFeatsCb.setEnabled(True)
            self.selectLayerLabel.setEnabled(True)
            self.selectLayerCb.setEnabled(True)
        else:
            if self.selectMethodCb.currentIndex() == 1:
                self.tool = self.select_features_freehand_tool
            else:
                self.tool = self.select_features_rectangle_tool

            self.selectLayerFeatsCb.setEnabled(False)
            self.selectLayerLabel.setEnabled(False)
            self.selectLayerCb.setEnabled(False)

    def on_select_area_button_pressed(self):
        iface.mapCanvas().setMapTool(self.tool)
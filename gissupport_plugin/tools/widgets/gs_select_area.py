# -*- coding: utf-8 -*-
import os
from enum import Enum
from functools import reduce

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QWidget, QSizePolicy
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QCursor, QPixmap, QColor
from qgis.core import (Qgis, QgsWkbTypes, QgsGeometry, QgsProject, QgsDistanceArea,
                       QgsCoordinateTransformContext, QgsUnitTypes, QgsPointXY,
                       QgsMapLayerProxyModel, QgsMapLayer
                       )
from qgis.gui import QgsRubberBand, QgsMapTool
from qgis.utils import iface

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'gs_select_area.ui'))

class GsSelectAreaOption(Enum):
    RECTANGLE = "Prostokątem"
    FREEHAND = "Swobodnie"
    LAYER = "Wskaż obiekty"

class GsSelectArea(QWidget, FORM_CLASS):
    methodChanged = pyqtSignal()
    # NOWY SYGNAŁ: Przekazuje gotową geometrię do downloadera
    geometryCreated = pyqtSignal(object) 

    def __init__(self, parent=None,
                 select_options: list = [GsSelectAreaOption.RECTANGLE.value, GsSelectAreaOption.FREEHAND.value, GsSelectAreaOption.LAYER.value],
                 select_layer_types: list = [QgsMapLayerProxyModel.PointLayer, QgsMapLayerProxyModel.LineLayer, QgsMapLayerProxyModel.PolygonLayer]
                 ):
        super(GsSelectArea, self).__init__(parent)
        self.setupUi(self)

        self.setSizePolicy(
            QSizePolicy.Minimum,
            QSizePolicy.Minimum
        )

        self.select_options = select_options
        self.select_layer_types = select_layer_types

        self.selectMethodCb.insertItems(0, self.select_options)

        self.selectLayerFeatsCb.setVisible(False)
        self.selectLayerLabel.setVisible(False)
        self.selectLayerCb.setVisible(False)

        self.selectLayerFeatsCb.setEnabled(False)
        self.selectLayerLabel.setEnabled(False)
        self.selectLayerCb.setEnabled(False)

        filters = reduce(lambda x, y: x | y, self.select_layer_types)
        self.selectLayerCb.setFilters(filters)
        self.selectLayerCb.layerChanged.connect(self.on_layer_changed)

        self.selectMethodCb.currentIndexChanged.connect(self.on_method_changed)

        self.select_features_tool = SelectFeaturesTool(self)
        self.select_features_rectangle_tool = SelectRectangleTool(self)
        self.select_features_freehand_tool = SelectFreehandTool(self)

        # Podłącznie narzędzi do nowego sygnału
        self.select_features_rectangle_tool.geometryEnded.connect(self.emit_geometry)
        self.select_features_freehand_tool.geometryEnded.connect(self.emit_geometry)
        self.select_features_tool.geometryEnded.connect(self.emit_geometry)

        self.selectAreaBtn.setCheckable(True)
        self.tool = self.select_features_rectangle_tool
        self.tool.setButton(self.selectAreaBtn)
        
        self.selectAreaBtn.clicked.connect(self.activate_tool)

        self.layer = None

    def emit_geometry(self, area, geom):
        """Przekazuje geometrię dalej przez główny sygnał widgetu"""
        self.geometryCreated.emit(geom)

    def activate_tool(self):
        iface.mapCanvas().setMapTool(self.tool)

    def on_method_changed(self):
        """Funkcja wywoływana przy zmianie metody wybierania obszaru"""
        method_name = self.selectMethodCb.currentText()

        if method_name == 'Wskaż obiekty':
            iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = self.select_features_tool

            self.selectAreaBtn.setVisible(False)
            self.selectAreaBtn.setEnabled(False)

            self.selectLayerFeatsCb.setVisible(True)
            self.selectLayerLabel.setVisible(True)
            self.selectLayerCb.setVisible(True)

            self.selectLayerFeatsCb.setEnabled(True)
            self.selectLayerLabel.setEnabled(True)
            self.selectLayerCb.setEnabled(True)

            self.tool.activate()

            if layer := self.selectLayerCb.currentLayer():
                if layer.type() == QgsMapLayer.VectorLayer:
                    try:
                        self.selectLayerCb.currentLayer().selectionChanged.disconnect(self.on_selection_changed)
                    except: pass
                    self.selectLayerCb.currentLayer().selectionChanged.connect(self.on_selection_changed)
                    count = self.selectLayerCb.currentLayer().selectedFeatureCount()
                else:
                    count = 0
            else:
                count = 0
            self.selectLayerFeatsCb.setText(f"Tylko zaznaczone obiekty [{count}]")

        else:
            if method_name == 'Swobodnie':
                self.tool = self.select_features_freehand_tool
            else:
                self.tool = self.select_features_rectangle_tool

            self.tool.setButton(self.selectAreaBtn)
            
            self.selectAreaBtn.setEnabled(True)
            self.selectAreaBtn.setVisible(True)

            self.selectLayerFeatsCb.setVisible(False)
            self.selectLayerLabel.setVisible(False)
            self.selectLayerCb.setVisible(False)

            self.selectLayerFeatsCb.setEnabled(False)
            self.selectLayerLabel.setEnabled(False)
            self.selectLayerCb.setEnabled(False)

        if self.selectAreaBtn.isChecked():
            iface.mapCanvas().setMapTool(self.tool)
        else:
            iface.mapCanvas().unsetMapTool(self.tool)

        self.methodChanged.emit()

    def on_layer_changed(self):
        layer = self.selectLayerCb.currentLayer()

        if layer:
            if layer.dataProvider().featureCount() == 0:
                return
            self.layer = layer
            try:
                self.layer.selectionChanged.disconnect(self.on_selection_changed)
            except: pass
            self.layer.selectionChanged.connect(self.on_selection_changed)
            self.on_selection_changed(self.layer.selectedFeatureIds())
            self.selectLayerFeatsCb.setEnabled(True)

        else:
            self.layer = None
            self.selectLayerFeatsCb.setEnabled(False)
            self.selectLayerFeatsCb.setChecked(False)
            self.selectLayerFeatsCb.setText("Tylko zaznaczone obiekty [0]")

    def on_selection_changed(self, selected_features):
        if self.layer:
             self.selectLayerFeatsCb.setText(f"Tylko zaznaczone obiekty [{self.layer.selectedFeatureCount()}]")

    def closeWidget(self):
        if self.tool:
            self.tool.reset()



class SelectRectangleTool(QgsMapTool):
    geometryChanged = pyqtSignal(float)
    geometryEnded = pyqtSignal(float, QgsGeometry)

    def __init__(self, parent):
        canvas = iface.mapCanvas()
        super(SelectRectangleTool, self).__init__(canvas)
        self.parent = parent

        # Konfiguracja narzędzia
        set_cursor(self)
        self.tempGeom = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.tempGeom.setColor(QColor(255, 0, 0, 100))
        self.tempGeom.setFillColor(QColor(255, 0, 0, 33))
        self.tempGeom.setWidth = 10

        self.startPoint = None
        self.area = 0
        self.geometry = QgsGeometry()

    def canvasPressEvent(self, e):
        if e.button() == Qt.LeftButton or e.button() == Qt.RightButton:
            self.startPoint = e.mapPoint()

    def canvasMoveEvent(self, e):
        if (e.buttons() == Qt.LeftButton or e.buttons() == Qt.RightButton) and self.startPoint:
            newPoint = e.mapPoint()
            pointA = QgsPointXY(self.startPoint.x(), newPoint.y())
            pointB = QgsPointXY(newPoint.x(), self.startPoint.y())
            self.tempGeom.reset(QgsWkbTypes.PolygonGeometry)
            self.tempGeom.addPoint(self.startPoint)
            self.tempGeom.addPoint(pointA)
            self.tempGeom.addPoint(newPoint)
            self.tempGeom.addPoint(pointB)

            area = QgsDistanceArea()
            area.setSourceCrs(QgsProject.instance().crs(), QgsCoordinateTransformContext())
            area.setEllipsoid('GRS80')
            self.geometry = self.tempGeom.asGeometry()
            rectangleArea = area.measureArea(self.geometry)
            self.area = area.convertAreaMeasurement(rectangleArea, QgsUnitTypes.AreaHectares)
            self.geometryChanged.emit(self.area)

    def canvasReleaseEvent(self, e):
        self.geometryEnded.emit(self.area, self.geometry)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.reset()

    def reset(self):
        self.tempGeom.reset(QgsWkbTypes.PolygonGeometry)
        self.startPoint = None

    def reset_geometry(self):
        self.tempGeom.reset(QgsWkbTypes.PolygonGeometry)
        self.startPoint = None

    def deactivate(self):
        self.parent.selectAreaBtn.setChecked(False)
        self.reset()
        super().deactivate()


class SelectFreehandTool(QgsMapTool):
    geometryChanged = pyqtSignal(float)
    geometryEnded = pyqtSignal(float, QgsGeometry)

    def __init__(self, parent):
        canvas = iface.mapCanvas()
        super(SelectFreehandTool, self).__init__(canvas)
        self.parent = parent

        # Konfiguracja narzędzia
        set_cursor(self)
        self.tempGeom = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.tempGeom.setColor(QColor(255, 0, 0, 100))
        self.tempGeom.setFillColor(QColor(255, 0, 0, 33))
        self.tempGeom.setWidth = 10

        self.drawing = False
        self.area = 0
        self.geometry = QgsGeometry()

    def canvasPressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.drawing is False:
                self.tempGeom.reset(QgsWkbTypes.PolygonGeometry)
                self.drawing = True
            self.tempGeom.addPoint(e.mapPoint())
            self.update_geometry()
            
        elif e.button() == Qt.RightButton and self.drawing:
            if self.tempGeom.numberOfVertices() > 2:
                self.tempGeom.removeLastPoint(0)
                self.drawing = False
                self.update_geometry()
                self.geometryEnded.emit(self.area, self.geometry)
            else:
                self.reset()

    def canvasMoveEvent(self, e):
        if self.tempGeom.numberOfVertices() > 0  and self.drawing:
            self.tempGeom.removeLastPoint(0)
            self.tempGeom.addPoint(self.toMapCoordinates(e.pos()))
            self.update_geometry()

    def update_geometry(self):
            area = QgsDistanceArea()
            area.setSourceCrs(QgsProject.instance().crs(), QgsCoordinateTransformContext())
            area.setEllipsoid('GRS80')
            self.geometry = self.tempGeom.asGeometry()
            rectangleArea = area.measureArea(self.geometry)
            self.area = area.convertAreaMeasurement(rectangleArea, QgsUnitTypes.AreaHectares)
            self.geometryChanged.emit(self.area)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.reset()

    def reset(self):
        self.tempGeom.reset(QgsWkbTypes.PolygonGeometry)

    def reset_geometry(self):
        self.tempGeom.reset(QgsWkbTypes.PolygonGeometry)

    def deactivate(self):
        self.parent.selectAreaBtn.setChecked(False)
        self.reset()
        super().deactivate()


class SelectFeaturesTool(QgsMapTool):
    geometryChanged = pyqtSignal(float)
    geometryEnded = pyqtSignal(float, QgsGeometry)

    def __init__(self, parent):
        canvas = iface.mapCanvas()
        super(SelectFeaturesTool, self).__init__(canvas)
        self.parent = parent

        # Konfiguracja narzędzia
        self.tempGeom = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)

        self.area = 0
        self.geometry = QgsGeometry()

    def activate(self):
        layer = self.parent.selectLayerCb.currentLayer()

        if layer is not None:            
            if self.parent.selectLayerFeatsCb.isChecked():
                features = layer.getSelectedFeatures()
            else:
                features = layer.getFeatures()
            
            geoms = [f.geometry() for f in features]
            if geoms:
                 self.geometry = QgsGeometry.unaryUnion(geoms)
                 area = QgsDistanceArea()
                 area.setSourceCrs(QgsProject.instance().crs(), QgsCoordinateTransformContext())
                 area.setEllipsoid('GRS80')
                 rectangleArea = area.measureArea(self.geometry)
                 self.area = area.convertAreaMeasurement(rectangleArea, QgsUnitTypes.AreaHectares)
                 self.geometryChanged.emit(self.area)
                 self.geometryEnded.emit(self.area, self.geometry)
        super().activate()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.reset()

    def reset(self):
        self.reset_geometry()

    def reset_geometry(self):
        self.area = 0
        self.geometry = QgsGeometry()
        self.tempGeom.reset(QgsWkbTypes.PolygonGeometry)

    def deactivate(self):
        self.parent.selectAreaBtn.setChecked(False)
        self.reset()
        super().deactivate()


def set_cursor(tool):
    tool.setCursor(QCursor(QPixmap(["16 16 2 1",
                                    "      c None",
                                    ".     c #000000",
                                    "                ",
                                    "        .       ",
                                    "        .       ",
                                    "      .....     ",
                                    "     .     .    ",
                                    "    .   .   .   ",
                                    "   .    .    .  ",
                                    "   .    .    .  ",
                                    " ... ... ... ...",
                                    "   .    .    .  ",
                                    "   .    .    .  ",
                                    "    .   .   .   ",
                                    "     .     .    ",
                                    "      .....     ",
                                    "        .       ",
                                    "        .       "])))
# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QCursor, QPixmap, QColor
from qgis.core import (Qgis, QgsWkbTypes, QgsGeometry, QgsProject, QgsDistanceArea,
                       QgsCoordinateTransformContext, QgsUnitTypes, QgsPointXY,
                        QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsVectorLayer
                       )
from qgis.gui import QgsRubberBand, QgsMapTool, QgsMapToolIdentifyFeature
from qgis.utils import iface


class SelectRectangleTool(QgsMapTool):
    geometryChanged = pyqtSignal(float)
    geometryEnded = pyqtSignal(float, QgsGeometry)

    def __init__(self, parent):
        canvas = iface.mapCanvas()
        super(SelectRectangleTool, self).__init__(canvas)
        self.parent = parent

        # Konfiguracja narzędzia
        set_cursor(self)
        self.tempGeom = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
        self.tempGeom.setColor(QColor(255, 0, 0, 100))
        self.tempGeom.setFillColor(QColor(255, 0, 0, 33))
        self.tempGeom.setWidth = 10

        self.startPoint = None
        self.area = 0
        self.geometry = QgsGeometry()

    def canvasPressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton or e.button() == Qt.MouseButton.RightButton:
            self.startPoint = e.mapPoint()

    def canvasMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton or e.buttons() == Qt.MouseButton.RightButton:
            newPoint = e.mapPoint()
            pointA = QgsPointXY(self.startPoint.x(), newPoint.y())
            pointB = QgsPointXY(newPoint.x(), self.startPoint.y())
            self.tempGeom.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
            self.tempGeom.addPoint(self.startPoint)
            self.tempGeom.addPoint(pointA)
            self.tempGeom.addPoint(newPoint)
            self.tempGeom.addPoint(pointB)

            area = QgsDistanceArea()
            area.setSourceCrs(QgsProject.instance().crs(), QgsCoordinateTransformContext())
            area.setEllipsoid('GRS80')

            rectangleArea = area.measureArea(self.tempGeom.asGeometry())
            rectangleAreaHectares = area.convertAreaMeasurement(rectangleArea, QgsUnitTypes.AreaUnit.AreaHectares)
            self.area = rectangleAreaHectares
            self.geometry = self.tempGeom.asGeometry()
            self.geometryChanged.emit(self.area)

    def canvasReleaseEvent(self, e):
        self.geometryEnded.emit(self.area, self.geometry)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reset()

    def reset(self):
        self.tempGeom.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
        self.startPoint = None
        iface.mapCanvas().unsetMapTool(self)

    def reset_geometry(self):
        self.tempGeom.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
        self.startPoint = None

    def deactivate(self):
        self.reset()


class SelectFreehandTool(QgsMapTool):
    geometryChanged = pyqtSignal(float)
    geometryEnded = pyqtSignal(float, QgsGeometry)

    def __init__(self, parent):
        canvas = iface.mapCanvas()
        super(SelectFreehandTool, self).__init__(canvas)
        self.parent = parent

        # Konfiguracja narzędzia
        set_cursor(self)
        self.tempGeom = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
        self.tempGeom.setColor(QColor(255, 0, 0, 100))
        self.tempGeom.setFillColor(QColor(255, 0, 0, 33))
        self.tempGeom.setWidth = 10

        self.area = 0
        self.geometry = QgsGeometry()

    def canvasPressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton or e.button() == Qt.MouseButton.RightButton:
            self.tempGeom.addPoint(e.mapPoint())

            area = QgsDistanceArea()
            area.setSourceCrs(QgsProject.instance().crs(), QgsCoordinateTransformContext())
            area.setEllipsoid('GRS80')

            rectangleArea = area.measureArea(self.tempGeom.asGeometry())
            rectangleAreaHectares = area.convertAreaMeasurement(rectangleArea, QgsUnitTypes.AreaUnit.AreaHectares)
            self.area = rectangleAreaHectares
            self.geometry = self.tempGeom.asGeometry()
            self.geometryChanged.emit(self.area)

    def canvasMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton or e.buttons() == Qt.MouseButton.RightButton:
            self.tempGeom.addPoint(e.mapPoint())

            area = QgsDistanceArea()
            area.setSourceCrs(QgsProject.instance().crs(), QgsCoordinateTransformContext())
            area.setEllipsoid('GRS80')

            rectangleArea = area.measureArea(self.tempGeom.asGeometry())
            rectangleAreaHectares = area.convertAreaMeasurement(rectangleArea, QgsUnitTypes.AreaUnit.AreaHectares)
            self.area = rectangleAreaHectares
            self.geometry = self.tempGeom.asGeometry()
            self.geometryChanged.emit(self.area)

    def canvasReleaseEvent(self, e):
        self.geometryEnded.emit(self.area, self.geometry)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reset()

    def reset(self):
        self.tempGeom.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
        self.parent.selectedToolLabel.setText("")
        self.parent.selectedToolLabel.setHidden(True)
        iface.mapCanvas().unsetMapTool(self)

    def reset_geometry(self):
        self.tempGeom.reset(QgsWkbTypes.GeometryType.PolygonGeometry)

    def deactivate(self):
        self.reset()


class SelectFeaturesTool(QgsMapToolIdentifyFeature):
    geometryChanged = pyqtSignal(float)
    geometryEnded = pyqtSignal(float, QgsGeometry)

    def __init__(self, parent):
        canvas = iface.mapCanvas()
        super(SelectFeaturesTool, self).__init__(canvas)
        self.parent = parent

        # Konfiguracja narzędzia
        set_cursor(self)

        self.tempGeom = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
        self.tempGeom.setColor(QColor(255, 0, 0, 100))
        self.tempGeom.setFillColor(QColor(255, 0, 0, 33))
        self.tempGeom.setWidth = 10

        self.tempGeom2 = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PolygonGeometry)

        self.area = 0
        self.geometry = QgsGeometry()
        self.objects = {}

    def canvasPressEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton or e.buttons() == Qt.MouseButton.RightButton:
            point = e.mapPoint()
            identify = self.identify(QgsGeometry().fromPointXY(point), self.TopDownAll, self.VectorLayer)

            if len(identify) > 0:
                feature_id = identify[0].mFeature.id()
                layer_id = identify[0].mLayer.id()

                if layer_id not in self.objects:
                    self.objects[layer_id] = []

                if feature_id not in self.objects[layer_id]:
                    self.objects[layer_id].append(feature_id)

                    geom = identify[0].mFeature.geometry()

                    layer_crs = identify[0].mLayer.crs()
                    crs_2180 = QgsCoordinateReferenceSystem.fromEpsgId(2180)
                    if layer_crs != crs_2180:
                        transformation = QgsCoordinateTransform(layer_crs, crs_2180, QgsProject.instance())
                        geom.transform(transformation)

                    self.tempGeom.addGeometry(geom, identify[0].mLayer)
                    self.tempGeom2.addGeometry(geom)

                    area = QgsDistanceArea()
                    area.setSourceCrs(QgsProject.instance().crs(), QgsCoordinateTransformContext())
                    area.setEllipsoid('GRS80')

                    rectangleArea = area.measureArea(self.tempGeom2.asGeometry())
                    rectangleAreaHectares = area.convertAreaMeasurement(rectangleArea, QgsUnitTypes.AreaUnit.AreaHectares)
                    self.area = rectangleAreaHectares
                    self.geometry = self.tempGeom2.asGeometry()
                    self.geometryChanged.emit(self.area)
                    self.geometryEnded.emit(self.area, self.geometry)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reset()

    def reset(self):
        self.reset_geometry()
        iface.mapCanvas().unsetMapTool(self)

    def reset_geometry(self):
        self.tempGeom.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
        self.tempGeom2.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
        self.objects = {}

    def deactivate(self):
        self.reset()


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
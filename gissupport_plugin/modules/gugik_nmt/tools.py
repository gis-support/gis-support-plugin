# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QInputDialog, QTableWidgetItem
from qgis.PyQt.QtGui import QCursor, QPixmap, QColor
from qgis.core import (QgsMapLayer, QgsWkbTypes, QgsGeometry, QgsProject, Qgis, QgsDistanceArea,
    QgsCoordinateTransformContext, QgsUnitTypes, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsTask, QgsApplication)
from qgis.gui import QgsRubberBand, QgsMapTool
from qgis.utils import iface

class IdentifyTool(QgsMapTool):
    """ Narzędzie identyfikacji wysokości """

    def __init__(self, parent):
        canvas = iface.mapCanvas()
        super(IdentifyTool, self).__init__(canvas)
        self.parent = parent
        
        set_cursor(self)

        self.tempGeom = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
        self.tempGeom.setColor(QColor('red'))
        self.tempGeom.setWidth = 5
        
    def canvasMoveEvent(self, e):
        if QgsProject.instance().crs().authid() != 'EPSG:2180':
            point92 = self.parent.coordsTransform(e.mapPoint(), 'EPSG:2180')
        else:
            point92 = e.mapPoint()
        if QgsProject.instance().crs().authid() != 'EPSG:4326':
            point84 = self.parent.coordsTransform(e.mapPoint(), 'EPSG:4326')
        else:
            point84 = e.mapPoint()
        x92, y92 = point92.x(), point92.y()
        x84, y84 = point84.x(), point84.y()
        self.parent.dbs92X.setValue(x92)
        self.parent.dbs92Y.setValue(y92)
        self.parent.dsbWgsX.setValue(x84)
        self.parent.dsbWgsY.setValue(y84)

    def canvasReleaseEvent(self, e):
        geom = QgsGeometry.fromPointXY(e.mapPoint())
        height = self.parent.getHeight(geom)
        if height:
            self.parent.dbsHeight.setValue(float(height))
            self.tempGeom.addPoint(e.mapPoint())
            self.parent.savedFeats.append({
                'geometry':geom, 
                'height':height
                })

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.tempGeom.reset(QgsWkbTypes.PointGeometry)
            if self.parent.savedFeats:
                self.parent.savedFeats = []
        elif e.key() == Qt.Key_Delete:
            self.tempGeom.removeLastPoint()
            if self.parent.savedFeats:
                del self.parent.savedFeats[-1]

    def reset(self):
        self.tempGeom.reset(QgsWkbTypes.PointGeometry)
        self.parent.savedFeats = []
    
    def deactivate(self):
        self.tempGeom.reset(QgsWkbTypes.PointGeometry)
        self.button().setChecked(False)

class ProfileTool(QgsMapTool):
    """ Narzędzie do tworzenia krzywej """

    def __init__(self, parent):
        canvas = iface.mapCanvas()
        super(ProfileTool, self).__init__(canvas)
        
        set_cursor(self)
        self.editing = False
        self.parent = parent
        self.task = None

        self.tempGeom = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self.tempGeom.setColor(QColor('red'))
        self.tempGeom.setWidth(2)

        self.tempLine = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self.tempLine.setColor(QColor('red'))
        self.tempLine.setWidth(2)
        self.tempLine.setLineStyle(Qt.DotLine)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete:
            pointsCount = self.tempLine.numberOfVertices() 
            if pointsCount > 2 and self.editing:
                self.tempGeom.removePoint(pointsCount-2)
                self.tempLine.removePoint(pointsCount-2)
                len_m = self.calculateDistance(self.tempGeom.asGeometry())
                self.parent.dsbLineLength.setValue(len_m)
                if self.tempGeom.numberOfVertices() == 1:
                    self.tempGeom.reset(QgsWkbTypes.LineGeometry)
                    self.tempLine.reset(QgsWkbTypes.LineGeometry)
                    self.parent.dsbLineLength.setValue(0)           
            else:
                self.reset()
        elif e.key() == Qt.Key_Escape:
            self.reset()

    def canvasMoveEvent(self, e):
        #Poruszanie" wierzchołkiem linii tymczasowej zgodnie z ruchem myszki
        if self.tempGeom.numberOfVertices()>1:
            point = e.snapPoint()
            self.tempLine.movePoint(point)

    def canvasReleaseEvent(self, e):
        point = e.snapPoint()
        if self.task:
            iface.messageBar().pushMessage('Wtyczka GUGiK NMT:', 'Trwa genrowanie profilu. Aby wygenerować następny poczekaj na pobranie danych', Qgis.Warning)
            return
        if e.button() == int(Qt.LeftButton):
            #Dodawanie kolejnych wierzchołków
            if not self.editing:
                #Nowy obiekt, pierwszy wierzchołek
                self.tempLine.reset(QgsWkbTypes.LineGeometry)
                self.tempGeom.reset(QgsWkbTypes.LineGeometry)
                self.editing = True
            self.tempGeom.addPoint(point)
            self.tempLine.addPoint(point)
            len_m = self.calculateDistance(self.tempGeom.asGeometry())
            self.parent.dsbLineLength.setValue(len_m)
        elif e.button() == int(Qt.RightButton):
            if self.tempGeom.numberOfVertices() < 2:
                return
            #Zakończenie rysowania obiektu
            self.tempLine.reset()
            self.editing = False
            geometry = self.tempGeom.asGeometry()
            errors = geometry.validateGeometry()
            if errors:
            #Niepoprawna geometria                    
                for error in errors:
                    if self.tempGeom.numberOfVertices() > 2:
                        iface.messageBar().pushMessage('Wtyczka GUGiK NMT:', 'Niepoprawna geometria', Qgis.Critical)
                    self.tempGeom.reset()
                return
            self.get_interval()

    def get_interval(self):
        interval, ok = QInputDialog.getDouble(self.parent, 'Podaj interwał', 'Interwał [m]:')
        if not ok:
            self.reset()
            return
        geom = self.tempGeom.asGeometry()
        
        activeCrs = QgsProject.instance().crs().authid()
        fromCrs = QgsCoordinateReferenceSystem(activeCrs)
        toCrs = QgsCoordinateReferenceSystem(2180)
        transformation = QgsCoordinateTransform(fromCrs, toCrs, QgsProject.instance())
        geom.transform(transformation)
        
        meters_len = geom.length()
        if meters_len <= interval:
            iface.messageBar().pushMessage('Wtyczka GUGiK NMT:', 'Długość linii krótsza lub równa podanemu interwałowi', Qgis.Critical, 5)
            self.reset()
            return
        num_points = meters_len/interval
        points_on_line = []
        max_interval = 0
        intervals = []
        for i in range(int(num_points)+1):
            points_on_line.append(geom.interpolate(float(max_interval)))
            intervals.append(max_interval)
            max_interval += interval
        data = {'points':points_on_line, 'intervals':intervals}
        self.task = QgsTask.fromFunction('Pobieranie wysokości dla przekroju...', self.generateProfileFromPoints, data=data)
        QgsApplication.taskManager().addTask(self.task)

    def generateProfileFromPoints(self, task: QgsTask, data):
        points_on_line = data.get('points')
        intervals = data.get('intervals')
        heights = []
        total = 100/len(points_on_line)
        for idx, pt in enumerate(points_on_line):
            height = self.parent.getHeight(pt, special=True)
            heights.append(height)
        try:
            self.task.setProgress( idx*total )
        except AttributeError as e:
            pass
        if heights and intervals:   
            self.fillTable(heights, intervals)
        self.parent.on_success.emit('Pomyślnie wygenerowano profil')
        self.task = None

    def fillTable(self, heights, intervals):
        for idx, interval in enumerate(intervals):
            self.parent.twData.setRowCount(idx+1)
            self.parent.twData.setItem(idx, 0, QTableWidgetItem(f'{interval}'))
            self.parent.twData.setItem(idx, 1, QTableWidgetItem(heights[idx]))

    def calculateDistance(self, geometry):
        distanceArea = QgsDistanceArea()
        distanceArea.setEllipsoid('GRS80')
        distanceArea.setSourceCrs(QgsProject.instance().crs(), QgsCoordinateTransformContext())
        length = distanceArea.measureLength(geometry)
        result = distanceArea.convertLengthMeasurement(length, QgsUnitTypes.DistanceMeters)
        return result
        
    def reset(self):
        self.tempLine.reset(QgsWkbTypes.LineGeometry)
        self.tempGeom.reset(QgsWkbTypes.LineGeometry)
        self.parent.dsbLineLength.setValue(0)
        self.parent.twData.setRowCount(0)

    def deactivate(self):
        self.reset()
        self.parent.dsbLineLength.setEnabled(False) 
        self.button().setChecked(False)


def set_cursor(tool):
    tool.setCursor( QCursor(QPixmap(["16 16 2 1",
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
        "        .       "])) )

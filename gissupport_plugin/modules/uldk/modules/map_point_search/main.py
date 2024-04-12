from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCursor
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsCoordinateTransformContext, QgsFeature, QgsPoint)
from qgis.gui import QgsMapToolEmitPoint
from qgis.utils import iface

from ...uldk.api import ULDKSearchLogger, ULDKSearchPoint, ULDKSearchPointWorker, ULDKPoint

CRS_2180 = QgsCoordinateReferenceSystem.fromEpsgId(2180)

class MapPointSearch(QgsMapToolEmitPoint):

    icon_path = ':/plugins/plugin/intersect.png'

    def __init__(self, parent, result_collector):
        self.parent = parent
        self.canvas = parent.canvas
        super(QgsMapToolEmitPoint, self).__init__(self.canvas)
        self.canvasClicked.connect(self.__search)

        self.result_collector = result_collector

        self.search_in_progress = False

    def __search(self, point):
        if self.search_in_progress:
            return

        canvas_crs = self.canvas.mapSettings().destinationCrs()
        if canvas_crs != CRS_2180:
            transformation = QgsCoordinateTransform(canvas_crs, CRS_2180, QgsCoordinateTransformContext()) 
            point = transformation.transform(point)

        x = point.x()
        y = point.y()
        srid = 2180

        uldk_search = ULDKSearchPoint(
            "dzialka",
            ("geom_wkt", "wojewodztwo", "powiat", "gmina", "obreb","numer","teryt")
        )

        uldk_search = ULDKSearchLogger(uldk_search)
        uldk_point = ULDKPoint(x,y,srid)
        worker = ULDKSearchPointWorker(uldk_search, (uldk_point,))
        self.worker = worker
        thread= QThread()
        self.thread = thread
        worker.moveToThread(thread)
        thread.started.connect(self.__on_search_started)
        thread.started.connect(worker.search)
        worker.finished.connect(lambda thread=thread, worker=worker: self.__thread_cleanup(thread, worker))
        worker.finished.connect(self.__handle_finished)
        worker.found.connect(self.__handle_found)
        worker.not_found.connect(self.__handle_not_found)

        thread.start()

    def __handle_found(self, uldk_response_row):
        try:
            added_feature = self.result_collector.update(uldk_response_row)
        except self.result_collector.BadGeometryException:
            iface.messageBar().pushCritical(
                "Wtyczka ULDK",f"Działka posiada niepoprawną geometrię")
        # self.found.emit(added_feature)

    def __handle_not_found(self, uldk_point, exception):
        iface.messageBar().pushCritical(
            "Wtyczka ULDK",f"Nie znaleziono działki - odpowiedź serwera: '{str(exception)}'")
        # self.not_found.emit(exception)

    def __handle_finished(self):
        self.search_in_progress = False
        self.setCursor(Qt.CrossCursor)
        # self.search_finished.emit()

    def __on_search_started(self):
        self.search_in_progress = True
        self.setCursor(Qt.WaitCursor)
        # self.search_started.emit()

    def __thread_cleanup(self, thread, worker):
        thread.quit()
        thread.wait()
        thread.deleteLater()
        worker.deleteLater()

    def toggle(self, enabled):
        if enabled:
            self.canvas.unsetMapTool(self)
        else:
            self.canvas.setMapTool(self)

    def get_icon(self):
        return self.icon_path

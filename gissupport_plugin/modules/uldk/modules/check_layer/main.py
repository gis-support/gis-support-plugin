import os
from urllib.request import urlopen

from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QVariant
from PyQt5.QtGui import QKeySequence, QPixmap
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsCoordinateTransformContext, QgsMapLayerProxyModel,
                       QgsProject, QgsVectorLayer, QgsField, QgsFeature)
from qgis.gui import QgsMessageBarItem
from qgis.utils import iface

from gissupport_plugin.modules.uldk.uldk.api import ULDKPoint, ULDKSearchLogger, ULDKSearchPoint, ULDKSearchPointWorker
from gissupport_plugin.modules.uldk.uldk.resultcollector import ResultCollector

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), "main_base.ui"
))

PLOTS_LAYER_DEFAULT_FIELDS = [
    QgsField("wojewodztwo", QVariant.String),
    QgsField("powiat", QVariant.String),
    QgsField("gmina", QVariant.String),
    QgsField("obreb", QVariant.String),
    QgsField("arkusz", QVariant.String),
    QgsField("nr_dzialki", QVariant.String),
    QgsField("teryt", QVariant.String),
    QgsField("pow_m2", QVariant.String),
]

CRS_2180 = QgsCoordinateReferenceSystem()
CRS_2180.createFromSrid(2180)


def get_obiekty_form(count):
    form = "obiekt"
    count = count
    if count == 1:
        pass
    elif 2 <= count <= 4:
        form = "obiekty"
    elif 5 <= count <= 20:
        form = "obiektów"
    else:
        units = count % 10
        if units in (2,3,4):
            form = "obiekty"
        else:
            form = "obiektów"
    return form


class UI(QtWidgets.QFrame, FORM_CLASS):

    icon_info_path = ':/plugins/plugin/info.png'

    def __init__(self, target_layout, parent = None):
        super().__init__(parent)

        self.setupUi(self)
        
        target_layout.layout().addWidget(self)

        self.layer_select.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        self.label_info_start.setPixmap(QPixmap(self.icon_info_path))
        self.label_info_start.setToolTip((
            "Sprawdzanie wielu obiektów może być czasochłonne. W tym czasie\n"
            "będziesz mógł korzystać z pozostałych funkcjonalności wtyczki,\n"
            "ale mogą one działać wolniej. Sprawdzanie obiektów działa również\n"
            "po zamknięciu wtyczki."))
        
        self.label_info_percent.setPixmap(QPixmap(self.icon_info_path))
        self.label_info_percent.setToolTip((
            "Narzędzie porównuje pole powierzchni działek.\n"
            "Parametr dokładności określa dopuszczalny % różnicy\n"
            "np. parametr 1% ignoruje różnicę powierzchni mniejszą niż 1%"))   

        self.frame_how_it_works.setToolTip((
            "Narzędzie sprawdza dopasowanie geometrii warstwy źródłowej do obiektów w ULDK."))   
        self.label_info_icon.setPixmap(QPixmap(self.icon_info_path))


class CheckLayer:

    def __init__(self, parent, target_layout, result_collector):
        self.parent = parent
        self.canvas = iface.mapCanvas()
        self.ui = UI(target_layout)
        self.__init_ui()

        self.result_collector = result_collector
        self.output = []
        self.output_features = []
        self.query_points = []

        self.search_in_progress = False

    def __init_ui(self):
        self.ui.button_start.clicked.connect(self.__search)
        self.ui.button_cancel.clicked.connect(self.__stop)
        self.__on_layer_changed(self.ui.layer_select.currentLayer())
        self.ui.layer_select.layerChanged.connect(self.__on_layer_changed)
        self.ui.label_status.setText("")
        self.ui.label_found_count.setText("")
        self.ui.label_not_found_count.setText("")

    def __on_layer_changed(self, layer):
        self.ui.button_start.setEnabled(False)
        if layer:
            if layer.dataProvider().featureCount() == 0:
                return
            self.source_layer = layer
            layer.selectionChanged.connect(self.__on_layer_features_selection_changed)
            self.ui.button_start.setEnabled(True)
            suggested_target_layer_name = "Wyniki sprawdzenia ULDK"
            self.ui.text_edit_target_layer_name.setText(suggested_target_layer_name)
            self.ui.button_start.setEnabled(True)
        else:
            self.source_layer = None
            self.ui.text_edit_target_layer_name.setText("")
            self.ui.checkbox_selected_only.setText("Tylko zaznaczone obiekty [0]")

    def __on_layer_features_selection_changed(self, selected_features):
        if not self.source_layer:
            selected_features = []
        self.ui.checkbox_selected_only.setText(f"Tylko zaznaczone obiekty [{len(selected_features)}]")

    def __stop(self):
        self.thread.requestInterruption()
        self.ui.button_cancel.setEnabled(False)
        self.ui.button_cancel.setText("Przerywanie...")

    def __search(self):
        if self.search_in_progress:
            return

        self.output = []
        self.output_features = []
        self.query_points = []

        uldk_search = ULDKSearchPoint(
            "dzialka",
            ("geom_wkt", "wojewodztwo", "powiat", "gmina", "obreb", "numer", "teryt")
        )
        uldk_search = ULDKSearchLogger(uldk_search)

        features = self.source_layer.getSelectedFeatures() if bool(self.ui.checkbox_selected_only.checkState()) else self.source_layer.getFeatures()
        for feature in features:
            output_feature = QgsFeature(feature)

            query_point = output_feature.geometry().pointOnSurface() 
            source_crs = self.source_layer.sourceCrs()
            if source_crs != CRS_2180:
                transformation = QgsCoordinateTransform(source_crs, CRS_2180, QgsCoordinateTransformContext()) 
                query_point.transform(transformation)

            self.output_features.append(output_feature)

            uldk_point = ULDKPoint(query_point.asPoint().x(), query_point.asPoint().y(), 2180)
            self.query_points.append(uldk_point)

        worker = ULDKSearchPointWorker(uldk_search, self.query_points)
        self.worker = worker
        thread= QThread()
        self.thread = thread
        worker.moveToThread(thread)

        worker.finished.connect(self.search)
        thread.started.connect(self.__on_search_started)
        thread.started.connect(worker.search)
        worker.finished.connect(lambda thread=thread, worker=worker: self.__thread_cleanup(thread, worker))
        worker.finished.connect(self.__handle_finished)
        worker.found.connect(self.__handle_found)
        worker.not_found.connect(self.__handle_not_found)

        thread.start()

    def __handle_found(self, uldk_response_row):
        self.output.append(uldk_response_row)

    def __handle_not_found(self, uldk_point, exception):
        self.output.append('')

    def __handle_finished(self):
        self.search_in_progress = False

    def __on_search_started(self):
        self.search_in_progress = True

    def __thread_cleanup(self, thread, worker):
        thread.quit()
        thread.wait()
        thread.deleteLater()
        worker.deleteLater()

    def search(self):

        crs = self.source_layer.crs().toWkt()
        output_fields = self.source_layer.fields()
        for field in PLOTS_LAYER_DEFAULT_FIELDS:
            output_fields.append(field)

        output_layer = QgsVectorLayer(f"Polygon?crs={crs}", self.ui.text_edit_target_layer_name.text(), "memory")
        output_data_provider = output_layer.dataProvider()
        output_layer.startEditing()
        output_data_provider.addAttributes(output_fields)
        output_layer.updateFields()
        output_layer.commitChanges()

        #print(f"len self.output: {len(self.output)}\n len self.output_features: {len(self.output_features)}\n len self.query_points: {len(self.query_points)}\n")

        for i in range(0, len(self.output)):
            # print(f"OBIEKT NR {i}\n\t\t", end='')
            # print(f"PUNKT: {self.query_points[i]}")
            # print(f"ULDK: {self.output[i]}\n\t\t", end='')
            # print(f"QGIS: {self.output_features[i].attributes()}\n", end='')
            # print("========================================")
            if self.output[i] == '':
                continue

            current_input_feature = self.output_features[i]
            current_input_feature.setFields(output_fields, initAttributes=False)

            current_uldk_feature = ResultCollector.uldk_response_to_qgs_feature(self.output[i])

            geometry = current_input_feature.geometry()
            source_crs = self.source_layer.sourceCrs()
            if source_crs != CRS_2180:
                transformation = QgsCoordinateTransform(source_crs, CRS_2180, QgsCoordinateTransformContext())
                geometry.transform(transformation)

            area_difference = abs(geometry.area() - current_uldk_feature.geometry().area())
            area_difference_tolerance = self.ui.input_percent.value()
            if area_difference > 0:
                area_difference_percent = (area_difference / geometry.area()) * 100
            else:
                area_difference_percent = 0

            if area_difference_percent <= area_difference_tolerance:
                current_input_feature["wojewodztwo"] = current_uldk_feature["wojewodztwo"]
                current_input_feature["powiat"] = current_uldk_feature["powiat"]
                current_input_feature["gmina"] = current_uldk_feature["gmina"]
                current_input_feature["obreb"] = current_uldk_feature["obreb"]
                current_input_feature["arkusz"] = current_uldk_feature["arkusz"]
                current_input_feature["nr_dzialki"] = current_uldk_feature["nr_dzialki"]
                current_input_feature["teryt"] = current_uldk_feature["teryt"]
                current_input_feature["pow_m2"] = current_uldk_feature["pow_m2"]
                output_layer.updateFeature(current_input_feature)

            #print(geometry.area(), current_uldk_feature.geometry().area(), area_difference_percent, area_difference)
            output_data_provider.addFeatures([current_input_feature])

        #output_data_provider.addFeatures(self.output_features)
        QgsProject.instance().addMapLayer(output_layer)


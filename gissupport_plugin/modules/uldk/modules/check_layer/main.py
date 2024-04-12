import os

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QThread, QVariant
from PyQt5.QtGui import QPixmap
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsCoordinateTransformContext, QgsMapLayerProxyModel,
                       QgsProject, QgsVectorLayer, QgsField, QgsFeature, NULL)
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

CRS_2180 = QgsCoordinateReferenceSystem.fromEpsgId(2180)


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
        self.output_responses = []
        self.output_responses_features = []
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

        self.output_responses = []
        self.output_responses_features = []
        self.query_points = []

        uldk_search = ULDKSearchPoint(
            "dzialka",
            ("geom_wkt", "wojewodztwo", "powiat", "gmina", "obreb", "numer", "teryt")
        )
        uldk_search = ULDKSearchLogger(uldk_search)

        source_crs = self.source_layer.sourceCrs()
        transformation = QgsCoordinateTransform(source_crs, CRS_2180, QgsCoordinateTransformContext()) 

        features = self.source_layer.getSelectedFeatures() if bool(self.ui.checkbox_selected_only.checkState()) else self.source_layer.getFeatures()
        for feature in features:
            output_feature = QgsFeature(feature)

            query_point = output_feature.geometry().pointOnSurface() 
            if source_crs != CRS_2180:
                query_point.transform(transformation)

            self.output_responses_features.append(output_feature)

            uldk_point = ULDKPoint(query_point.asPoint().x(), query_point.asPoint().y(), 2180)
            self.query_points.append(uldk_point)

        worker = ULDKSearchPointWorker(uldk_search, self.query_points)
        self.worker = worker
        thread = QThread()
        self.thread = thread
        worker.moveToThread(thread)

        worker.finished.connect(self.process_results)
        thread.started.connect(self.__on_search_started)
        thread.started.connect(worker.search)
        worker.finished.connect(lambda thread=thread, worker=worker: self.__thread_cleanup(thread, worker))
        worker.finished.connect(self.__handle_finished)
        worker.found.connect(self.__handle_found)
        worker.not_found.connect(self.__handle_not_found)
        worker.interrupted.connect(self.__handle_interrupted)
        worker.interrupted.connect(lambda thread=thread, worker=worker: self.__thread_cleanup(thread, worker))

        thread.start()

    def __handle_found(self, uldk_response_row):
        self.output_responses.append(uldk_response_row)
        self.progressed_count += 1
        self.found_count += 1
        self.ui.progress_bar.setValue(int(self.progressed_count / len(self.query_points) * 100))
        self.ui.label_status.setText(f"Przetworzono {self.progressed_count} z {len(self.query_points)} obiektów")
        self.ui.label_found_count.setText(f"Znaleziono: {self.found_count}")

    def __handle_not_found(self, uldk_point, exception):
        self.output_responses.append('')
        self.progressed_count += 1
        self.not_found_count += 1
        self.ui.progress_bar.setValue(int(self.progressed_count / len(self.query_points) * 100))
        self.ui.label_status.setText(f"Przetworzono {self.progressed_count} z {len(self.query_points)} obiektów")
        self.ui.label_not_found_count.setText(f"Nie znaleziono: {self.not_found_count}")

    def __handle_finished(self):
        self.search_in_progress = False
        self.ui.button_start.setEnabled(True)
        self.ui.button_cancel.setEnabled(False)
        self.ui.progress_bar.setValue(0)

    def __on_search_started(self):
        self.search_in_progress = True
        self.ui.button_start.setEnabled(False)
        self.ui.button_cancel.setEnabled(True)
        self.ui.progress_bar.setValue(0)
        self.progressed_count = 0
        self.found_count = 0
        self.not_found_count = 0

        self.ui.label_status.setText(f"Przetworzono {self.progressed_count} z {len(self.query_points)} obiektów")
        self.ui.label_found_count.setText(f"Znaleziono: {self.found_count}")
        self.ui.label_not_found_count.setText(f"Nie znaleziono: {self.not_found_count}")

    def __thread_cleanup(self, thread, worker):
        thread.quit()
        thread.wait()
        thread.deleteLater()
        worker.deleteLater()

    def __handle_interrupted(self):
        self.search_in_progress = False
        self.ui.button_start.setEnabled(True)
        self.ui.button_cancel.setText("Anuluj")
        self.ui.button_cancel.setEnabled(False)
        self.ui.progress_bar.setValue(0)

    def process_results(self):

        crs = self.source_layer.crs().toWkt()

        output_layer = QgsVectorLayer(f"Polygon?crs={crs}", self.ui.text_edit_target_layer_name.text(), "memory")
        output_data_provider = output_layer.dataProvider()
        output_data_provider.addAttributes(self.source_layer.fields().toList())
        output_data_provider.addAttributes(PLOTS_LAYER_DEFAULT_FIELDS)
        output_layer.updateFields()
        fields = output_layer.fields()

        source_crs = self.source_layer.sourceCrs()
        transformation = QgsCoordinateTransform(source_crs, CRS_2180, QgsCoordinateTransformContext())

        area_difference_tolerance = self.ui.input_percent.value()

        for idx, feature in enumerate(self.output_responses):
            if self.output_responses[idx] == '':
                continue

            current_feature = self.output_responses_features[idx]
            current_uldk_feature = ResultCollector.uldk_response_to_qgs_feature(feature)

            current_feature.setFields(fields, False)
            current_feature.setAttributes(
                current_feature.attributes() + [NULL for _ in range(len(PLOTS_LAYER_DEFAULT_FIELDS))]
            )

            geometry = current_feature.geometry()

            if source_crs != CRS_2180:
                geometry.transform(transformation)

            area_difference = abs(geometry.area() - current_uldk_feature.geometry().area())
            area_difference_percent = (area_difference / geometry.area()) * 100

            if area_difference_percent <= area_difference_tolerance:
                for field in PLOTS_LAYER_DEFAULT_FIELDS:
                    field_index = fields.indexFromName(field.name())
                    uldk_field_index = current_uldk_feature.fields().indexFromName(field.name())
                    current_feature[field_index] = current_uldk_feature[uldk_field_index]

            output_data_provider.addFeature(current_feature)

        QgsProject.instance().addMapLayer(output_layer)

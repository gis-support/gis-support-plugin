import os

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QPixmap
from qgis.core import (QgsCoordinateReferenceSystem, QgsMapLayerProxyModel,
                       QgsProject)
from qgis.gui import QgsMessageBarItem
from qgis.utils import iface

from .worker import LayerImportWorker

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), "main_base.ui"
))

CRS_2180 = QgsCoordinateReferenceSystem.fromEpsgId(2180)

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

        self.layer_select.setFilters(QgsMapLayerProxyModel.PointLayer | QgsMapLayerProxyModel.LineLayer | QgsMapLayerProxyModel.PolygonLayer)

        self.label_info_start.setPixmap(QPixmap(self.icon_info_path))
        self.label_info_start.setToolTip((
            "Wyszukiwanie wielu obiektów może być czasochłonne. W tym czasie\n"
            "będziesz mógł korzystać z pozostałych funkcjonalności wtyczki,\n"
            "ale mogą one działać wolniej. Wyszukiwanie obiektów działa również\n"
            "po zamknięciu wtyczki."))

        self.frame_how_it_works.setToolTip((
            "Narzędzie wyszukuje działki\n"
            "które mają wspólną geometrię z warstwą punktową wczytaną do QGIS."))   
        self.label_info_icon.setPixmap(QPixmap(self.icon_info_path))

class LayerImport:

    def __init__(self, parent, target_layout):
        self.parent = parent
        self.canvas = iface.mapCanvas()
        self.ui = UI(target_layout)
        self.__init_ui()
        
    def search(self):
        layer = self.source_layer
        
        target_layer_name = self.ui.text_edit_target_layer_name.text()

        selected_only = bool(self.ui.checkbox_selected_only.checkState())
        selected_field_names = self.ui.combobox_fields_select.checkedItems()
        fields_to_copy = [ field for field in layer.dataProvider().fields()
                            if field.name() in selected_field_names ]

        features_iterator = layer.getSelectedFeatures() if selected_only else layer.getFeatures()
        count = sum(1 for i in features_iterator)
        self.source_features_count = count

        self.__cleanup_before_search()

        self.worker = LayerImportWorker(layer, selected_only, target_layer_name, fields_to_copy)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.worker.progressed.connect(self.__progressed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.__handle_finished)
        self.worker.interrupted.connect(self.__handle_interrupted)
        self.worker.interrupted.connect(self.thread.quit)
        self.thread.started.connect(self.worker.search)

        self.thread.start()


        self.ui.label_status.setText(f"Trwa wyszukiwanie {count} obiektów...")
    
    def __init_ui(self):
        self.ui.button_start.clicked.connect(self.search)
        self.ui.button_cancel.clicked.connect(self.__stop)
        self.__on_layer_changed(self.ui.layer_select.currentLayer())
        self.ui.layer_select.layerChanged.connect(self.__on_layer_changed)
        self.ui.label_status.setText("")
        self.ui.label_found_count.setText("")
        self.ui.label_not_found_count.setText("")

    def __on_layer_changed(self, layer):
        self.ui.combobox_fields_select.clear()
        self.ui.button_start.setEnabled(False)
        if layer:
            if layer.dataProvider().featureCount() == 0:
                return
            self.source_layer = layer
            layer.selectionChanged.connect(self.__on_layer_features_selection_changed)
            layer.updatedFields.connect(self.__fill_combobox_fields_select)
            self.ui.button_start.setEnabled(True)
            current_layer_name = layer.sourceName()
            suggested_target_layer_name = f"{current_layer_name} - Działki ULDK"
            fields = layer.dataProvider().fields()
            self.ui.text_edit_target_layer_name.setText(suggested_target_layer_name)
            self.ui.combobox_fields_select.addItems(map(lambda x: x.name(), fields))
            self.ui.button_start.setEnabled(True)
        else:
            self.source_layer = None
            self.ui.text_edit_target_layer_name.setText("")
            self.ui.checkbox_selected_only.setText("Tylko zaznaczone obiekty [0]")
    
    def __on_layer_features_selection_changed(self, selected_features):
        if not self.source_layer:
            selected_features = []
        self.ui.checkbox_selected_only.setText(f"Tylko zaznaczone obiekty [{len(selected_features)}]")

    def __fill_combobox_fields_select(self):
        self.ui.combobox_fields_select.clear()
        fields = self.source_layer.dataProvider().fields()
        self.ui.combobox_fields_select.addItems(map(lambda x: x.name(), fields))

    def __progressed(self, layer_found, layer_not_found, found, omitted_count, saved, feature_processed):
        if saved:
            self.saved_count += 1
        if found and feature_processed:
            self.found_count += 1
        elif not found:
            self.not_found_count += 1
        if feature_processed:
            if layer_found.dataProvider().featureCount():
                self.__reload_and_add_layer(layer_found)

            if layer_not_found.dataProvider().featureCount():
                self.__reload_and_add_layer(layer_not_found)

        self.omitted_count += omitted_count
        progressed_count = self.found_count
        if self.worker.count_not_found_as_progressed:
            progressed_count += self.not_found_count

        self.ui.progress_bar.setValue(int(progressed_count/self.source_features_count*100))
        self.ui.label_status.setText(f"Postęp przetwarzania: {progressed_count} z {self.source_features_count} obiektów")
        found_message = f"Znalezione działki: {self.saved_count}"
        if self.omitted_count:
            found_message += f" (pominięto: {self.omitted_count})"

        self.ui.label_found_count.setText(found_message)
        self.ui.label_not_found_count.setText(f"Brak dopasowań: {self.not_found_count}")

    def __handle_finished(self, layer_found, layer_not_found):
        self.__cleanup_after_search()
        iface.messageBar().pushWidget(QgsMessageBarItem("Wtyczka GIS Support",
            f"Import z warstwy: zakończono wyszukiwanie. Zapisano {self.saved_count} {get_obiekty_form(self.saved_count)} do warstwy <b>{self.ui.text_edit_target_layer_name.text()}</b>"))

    def __handle_interrupted(self, layer_found, layer_not_found):
        self.__cleanup_after_search()

        if layer_found.dataProvider().featureCount():
            self.__reload_and_add_layer(layer_found)
        if layer_not_found.dataProvider().featureCount():
            self.__reload_and_add_layer(layer_not_found)

    def __cleanup_after_search(self):
        self.__set_controls_enabled(True)
        self.ui.button_cancel.setText("Anuluj")
        self.ui.button_cancel.setEnabled(False)   
        self.ui.progress_bar.setValue(0)  

    def __cleanup_before_search(self):
        self.__set_controls_enabled(False)
        self.ui.button_cancel.setEnabled(True)
        self.ui.label_status.setText("")
        self.ui.label_found_count.setText("")
        self.ui.label_not_found_count.setText("")

        self.found_count = 0
        self.not_found_count = 0
        self.omitted_count = 0
        self.saved_count = 0

    def __set_controls_enabled(self, enabled):
        self.ui.text_edit_target_layer_name.setEnabled(enabled)
        self.ui.button_start.setEnabled(enabled)
        self.ui.layer_select.setEnabled(enabled)

    def __stop(self):
        self.thread.requestInterruption()
        self.ui.button_cancel.setEnabled(False)
        self.ui.button_cancel.setText("Przerywanie...")

    def __reload_and_add_layer(self, layer):
        layer.reload()
        if not QgsProject.instance().mapLayersByName(layer.name()):
            QgsProject.instance().addMapLayer(layer)

import csv
import os
from collections import defaultdict

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import QThread, QVariant
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem, QFileDialog
from qgis.gui import QgsMessageBarItem
from qgis.utils import iface
from qgis.core import QgsField, QgsMapLayerProxyModel, QgsVectorLayer

from gissupport_plugin.modules.uldk.uldk.api import ULDKSearchParcel, ULDKSearchWorker, ULDKSearchLogger
from gissupport_plugin.modules.uldk.uldk.resultcollector import PLOTS_LAYER_DEFAULT_FIELDS
from gissupport_plugin.modules.uldk.uldk.resultcollector import ResultCollectorMultiple

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), "main_base.ui"
))

class UI(QtWidgets.QFrame, FORM_CLASS):

    icon_info_path = ':/plugins/plugin/info.png'

    def __init__(self, parent, target_layout):
        super().__init__(parent)

        self.setupUi(self)
        self.initGui(target_layout)

    def initGui(self, target_layout):
        target_layout.layout().addWidget(self)

        self.label_info_start.setPixmap(QPixmap(self.icon_info_path))
        self.label_info_start.setToolTip((
            "Wyszukiwanie wielu obiektów może być czasochłonne. W tym czasie\n"
            "będziesz mógł korzystać z pozostałych funkcjonalności wtyczki,\n"
            "ale mogą one działać wolniej. Wyszukiwanie obiektów działa również\n"
            "po zamknięciu wtyczki."))
        self.label_info_column.setPixmap(QPixmap(self.icon_info_path))
        self.label_info_column.setToolTip((
            "Kolumna zawierająca kody TERYT działek, \n"
            "przykład poprawnego kodu: 141201_1.0001.1867/2"))

        self.label_info_icon.setPixmap(QPixmap(self.icon_info_path))
        self.label_info_icon.setToolTip((
            "Narzędzie wyszukuje działki na podstawie listy:\n"
            "załaduj warstwę z projektu, wskaż kolumnę z TERYT i uruchom wyszukiwanie."))

class CSVImport:

    def __init__(self, parent, target_layout):
        self.parent = parent
        self.ui = UI(parent.dockwidget, target_layout)

        self.file_path = None

        self.__init_ui()

        uldk_search = ULDKSearchParcel("dzialka",
             ("geom_wkt", "wojewodztwo", "powiat", "gmina", "obreb","numer","teryt"))

        self.uldk_search = ULDKSearchLogger(uldk_search)

        self.fields_to_add = []

    def start_import(self) -> None:
        self.__cleanup_before_search()

        teryts = {}
        self.additional_attributes = defaultdict(list)
        self.fields_to_add = []

        teryt_column = self.ui.combobox_teryt_column.currentText()
        source_layer = self.ui.layer_select.currentLayer()

        fields = source_layer.fields()
        teryt_idx = fields.lookupField(teryt_column)


        default_field_names = [f.name() for f in PLOTS_LAYER_DEFAULT_FIELDS]
        additional_fields_names = [name for name in fields.names()
                                   if name != teryt_column and
                                   name not in default_field_names]
        additional_indices = []
        if additional_fields_names:
            for name in additional_fields_names:
                src_field = fields.field(name)
                idx = fields.lookupField(name)
                if idx != -1:
                    additional_indices.append(idx)
                    new_field = QgsField(src_field.name(), src_field.type(), src_field.typeName())
                    self.fields_to_add.append(new_field)

        for i, row in enumerate(source_layer.getFeatures()):
            teryt = row.attributes()[teryt_idx]
            teryts[i] = {"teryt": teryt}
            if additional_indices:
                for idx in additional_indices:
                    self.additional_attributes[i].append(row.attributes()[idx])

        dock = self.parent.dockwidget
        if dock.radioExistingLayer.isChecked() and dock.comboLayers.currentLayer():
            layer = dock.comboLayers.currentLayer()
        else:
            layer_name = self.ui.text_edit_layer_name.text()
            layer = ResultCollectorMultiple.default_layer_factory(
                name = layer_name,
                custom_properties = {"ULDK": layer_name},
                additional_fields=self.fields_to_add
            )

        self.result_collector = ResultCollectorMultiple(self.parent, layer)
        self.features_found = []
        self.csv_rows_count = len(teryts)

        self.worker = ULDKSearchWorker(self.uldk_search, teryts)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.worker.found.connect(self.__handle_found)
        self.worker.found.connect(self.__progressed)
        self.worker.not_found.connect(self.__handle_not_found)
        self.worker.not_found.connect(self.__progressed)
        self.worker.found.connect(self.__progressed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.__handle_finished)
        self.worker.interrupted.connect(self.__handle_interrupted)
        self.worker.interrupted.connect(self.thread.quit)
        self.thread.started.connect(self.worker.search)

        self.thread.start()

        self.ui.label_status.setText(f"Trwa wyszukiwanie {self.csv_rows_count} obiektów...")

    def __init_ui(self) -> None:
        self.ui.button_start.clicked.connect(self.start_import)
        self.ui.label_status.setText("")
        self.ui.label_found_count.setText("")
        self.ui.label_not_found_count.setText("")
        self.ui.button_cancel.clicked.connect(self.__stop)
        self.ui.layer_select.setFilters(QgsMapLayerProxyModel.Filter.VectorLayer)

        self.ui.layer_select.layerChanged.connect(self.ui.combobox_teryt_column.setLayer)
        self.ui.layer_select.layerChanged.connect(self._auto_select_teryt_column)
        self.ui.layer_select.layerChanged.connect(self._toggle_target_input)
        self.ui.layer_select.layerChanged.connect(
            lambda layer: self.ui.button_start.setEnabled(bool(layer))
        )

        self.ui.button_save_not_found.clicked.connect(self._export_table_errors_to_csv)
        self.__init_table()
        self._auto_select_teryt_column(self.ui.layer_select.currentLayer())

        dock = self.parent.dockwidget
        dock.radioExistingLayer.toggled.connect(self._toggle_target_input)
        dock.comboLayers.layerChanged.connect(self._toggle_target_input)

        self._toggle_target_input()


    def __init_table(self):
        table = self.ui.table_errors
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(("TERYT", "Treść błędu"))
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        teryt_column_size = table.width()/3
        header.resizeSection(0, 200)

    def _auto_select_teryt_column(self, layer: QgsVectorLayer) -> None:
        """Automatycznie szuka pola TERYT w nowo wybranej warstwie."""
        if not layer:
            return

        fields = layer.fields()
        keywords = ['teryt', 'id_teryt', 'kod_teryt']
        for key in keywords:
            idx = fields.lookupField(key)
            if idx != -1:
                self.ui.combobox_teryt_column.setField(fields.at(idx).name())
                break

    def _toggle_target_input(self) -> None:
        dock = self.parent.dockwidget
        is_existing = dock.radioExistingLayer.isChecked()

        if is_existing:
            self.ui.text_edit_layer_name.setEnabled(False)
            target_layer = dock.comboLayers.currentLayer()

            if target_layer:
                self.ui.text_edit_layer_name.setText(target_layer.name())
            else:
                self.ui.text_edit_layer_name.setText("Wybierz warstwę docelową...")
        else:
            self.ui.text_edit_layer_name.setEnabled(True)
            source_layer = self.ui.layer_select.currentLayer()
            if source_layer:
                self.ui.text_edit_layer_name.setText(f"{source_layer.name()} - Działki ULDK")
            else:
                self.ui.text_edit_layer_name.setText("")

    def __handle_found(self, uldk_response_dict: dict[int, list]) -> None:
        current_features = []
        for id_, uldk_response_rows in uldk_response_dict.items():
            for row in uldk_response_rows:
                try:
                    attributes = self.additional_attributes.get(id_, [])
                    feature = self.result_collector.uldk_response_to_qgs_feature(
                        row,
                        attributes,
                        additional_fields_defs=self.fields_to_add
                    )
                except self.result_collector.BadGeometryException as error:
                    e = self.result_collector.BadGeometryException(error.feature, "Niepoprawna geometria")
                    self._handle_bad_geometry(error.feature, e)
                    continue
                except self.result_collector.ResponseDataException as e:
                    e = self.result_collector.ResponseDataException("Błąd przetwarzania danych wynikowych")
                    self._handle_data_error(self.worker.teryt_ids[id_]["teryt"], e)
                    continue

                current_features.append(feature)
                self.found_count += 1

        if current_features:
            self.result_collector.update_with_features(current_features)

    def __handle_not_found(self, teryt, exception):
        self._add_table_errors_row(teryt, str(exception))
        self.not_found_count += 1

    def _handle_bad_geometry(self, feature, exception):
        self._add_table_errors_row(feature.attribute("teryt"), str(exception))
        self.not_found_count += 1

    def _handle_data_error(self, teryt, exception):
        self._add_table_errors_row(teryt, str(exception))
        self.not_found_count += 1

    def __progressed(self):
        found_count = self.found_count
        not_found_count = self.not_found_count
        progressed_count = found_count + not_found_count
        self.ui.progress_bar.setValue(int(progressed_count/self.csv_rows_count*100))
        self.ui.label_status.setText("Przetworzono {} z {} obiektów".format(progressed_count, self.csv_rows_count))
        self.ui.label_found_count.setText("Znaleziono: {}".format(found_count))
        self.ui.label_not_found_count.setText("Nie znaleziono: {}".format(not_found_count))

    def __handle_finished(self):
        form = "obiekt"
        found_count = self.found_count
        if found_count == 1:
            pass
        elif 2 <= found_count <= 4:
            form = "obiekty"
        elif 5 <= found_count <= 15:
            form = "obiektów"
        else:
            units = found_count % 10
            if units in (2,3,4):
                form = "obiekty"
            else:
                form = "obiektów"

        iface.messageBar().pushWidget(QgsMessageBarItem("Wtyczka GIS Support",
            f"Wyszukiwanie z listy: zakończono wyszukiwanie. Zapisano {found_count} {form} do warstwy <b>{self.ui.text_edit_layer_name.text()}</b>"))
        if self.not_found_count > 0:
            self.ui.button_save_not_found.setEnabled(True)

        self.__cleanup_after_search()

    def __handle_interrupted(self):
        iface.messageBar().pushWidget(QgsMessageBarItem("Wtyczka GIS Support",
            f"Wyszukiwanie przerwane. Zapisano {self.found_count} obiektów."))
        self.__cleanup_after_search()

    def _export_table_errors_to_csv(self):
        count = self.ui.table_errors.rowCount()
        path, _ = QFileDialog.getSaveFileName(filter='*.csv')
        if path:
            with open(path, 'w') as f:
                writer = csv.writer(f, delimiter=',')
                writer.writerow([
                    self.ui.table_errors.horizontalHeaderItem(0).text(),
                    self.ui.table_errors.horizontalHeaderItem(1).text()
                ])
                for row in range(0, count):
                    teryt = self.ui.table_errors.item(row, 0).text()
                    error = self.ui.table_errors.item(row, 1).text()
                    writer.writerow([teryt, error])
                iface.messageBar().pushWidget(QgsMessageBarItem("Wtyczka GIS Support",
                    "Pomyślnie wyeksportowano nieznalezione działki."))

    def _add_table_errors_row(self, teryt, exception_message):
        row = self.ui.table_errors.rowCount()
        self.ui.table_errors.insertRow(row)
        self.ui.table_errors.setItem(row, 0, QTableWidgetItem(teryt))
        self.ui.table_errors.setItem(row, 1, QTableWidgetItem(exception_message))

    def __cleanup_after_search(self):
        self.__set_controls_enabled(True)
        self.ui.button_cancel.setText("Anuluj")
        self.ui.button_cancel.setEnabled(False)
        self.ui.progress_bar.setValue(0)

    def __cleanup_before_search(self):
        self.__set_controls_enabled(False)
        self.ui.button_cancel.setEnabled(True)
        self.ui.button_save_not_found.setEnabled(False)
        self.ui.table_errors.setRowCount(0)
        self.ui.label_status.setText("")
        self.ui.label_found_count.setText("")
        self.ui.label_not_found_count.setText("")

        self.found_count = 0
        self.not_found_count = 0

    def __set_controls_enabled(self, enabled: bool) -> None:
        dock = self.parent.dockwidget
        is_existing = dock.radioExistingLayer.isChecked()
        self.ui.text_edit_layer_name.setEnabled(enabled and not is_existing)
        self.ui.button_start.setEnabled(enabled)
        self.ui.layer_select.setEnabled(enabled)
        self.ui.combobox_teryt_column.setEnabled(enabled)

    def __stop(self):
        self.thread.requestInterruption()
        self.ui.button_cancel.setEnabled(False)
        self.ui.button_cancel.setText("Przerywanie...")

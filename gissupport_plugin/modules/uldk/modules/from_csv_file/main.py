import csv
import os

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem, QFileDialog
from qgis.gui import QgsMessageBarItem
from qgis.utils import iface
from qgis.core import QgsFeature

from gissupport_plugin.modules.uldk.uldk.api import ULDKSearchParcel, ULDKSearchWorker, ULDKSearchLogger
from gissupport_plugin.modules.uldk.uldk.resultcollector import ResultCollectorMultiple

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), "main.ui"
))

class UI(QtWidgets.QFrame, FORM_CLASS):

    icon_info_path = ':/plugins/plugin/info.png'

    def __init__(self, parent, target_layout):
        super().__init__(parent)

        self.setupUi(self)
        self.initGui(target_layout)

    def initGui(self, target_layout):
        target_layout.layout().addWidget(self)

        self.label_info_icon.setPixmap(QPixmap(self.icon_info_path))
        self.label_info_icon.setToolTip((
            "Narzędzie wyszukuje działki na podstawie pliku CSV:\n"
            "załaduj plik CSV z dysku, wskaż kolumnę z TERYT i uruchom wyszukiwanie."))

        self.label_info_column.setPixmap(QPixmap(self.icon_info_path))
        self.label_info_column.setToolTip((
            "Kolumna zawierająca kody TERYT działek, \n"
            "przykład poprawnego kodu: 141201_1.0001.1867/2"))

        self.label_info_start.setPixmap(QPixmap(self.icon_info_path))
        self.label_info_start.setToolTip((
            "Wyszukiwanie wielu obiektów może być czasochłonne. W tym czasie\n"
            "będziesz mógł korzystać z pozostałych funkcjonalności wtyczki,\n"
            "ale mogą one działać wolniej. Wyszukiwanie obiektów działa również\n"
            "po zamknięciu wtyczki."))


class FromCSVFile:

    def __init__(self, parent, target_layout):
        self.parent = parent
        self.ui = UI(parent.dockwidget, target_layout)

        self.file_path = None
        self.csv_data = []
        self.csv_headers = []

        self.__init_ui()

        uldk_search = ULDKSearchParcel("dzialka",
             ("geom_wkt", "wojewodztwo", "powiat", "gmina", "obreb","numer","teryt"))

        self.uldk_search = ULDKSearchLogger(uldk_search)

    def start_import(self) -> None:
        self.__cleanup_before_search()

        teryts = {}

        # Pobranie indeksu wybranej kolumny TERYT
        teryt_column = self.ui.combobox_teryt_column.currentText()
        teryt_index = self.csv_headers.index(teryt_column)

        # Mapowanie danych z CSV do słownika dla Workera ULDK
        for i, row in enumerate(self.csv_data):
            if len(row) <= teryt_index:
                continue
            teryts[i] = {"teryt": row[teryt_index]}

        # Decyzja o warstwie docelowej (istniejąca lub nowa)
        dock = self.parent.dockwidget
        if dock.radioExistingLayer.isChecked() and dock.comboLayers.currentLayer():
            layer = dock.comboLayers.currentLayer()
        else:
            layer_name = self.ui.text_edit_layer_name.text() or "Działki z CSV"
            layer = ResultCollectorMultiple.default_layer_factory(
                name=layer_name,
                custom_properties={"ULDK": "from_csv_file"},
            )

        self.result_collector = ResultCollectorMultiple(self.parent, layer)
        self.csv_rows_count = len(teryts)

        self.worker = ULDKSearchWorker(self.uldk_search, teryts)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)

        # Podłączenie sygnałów postępu i zakończenia
        self.worker.found.connect(self.__handle_found)
        self.worker.not_found.connect(self.__handle_not_found)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.__handle_finished)

        # Aktualizacja paska postępu
        self.worker.found.connect(self.__progressed)
        self.worker.not_found.connect(self.__progressed)

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
        self.ui.button_save_not_found.clicked.connect(self._export_table_errors_to_csv)

        self.ui.file_select.fileChanged.connect(self.__on_file_changed)

        dock = self.parent.dockwidget
        dock.radioExistingLayer.toggled.connect(self._toggle_target_input)
        dock.comboLayers.layerChanged.connect(self._toggle_target_input)

        self._toggle_target_input()
        self.__init_table()

    def __init_table(self) -> None:
        table = self.ui.table_errors
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(("TERYT", "Treść błędu"))
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.resizeSection(0, 200)

    def __on_file_changed(self, file_path: str) -> None:
        self.file_path = file_path

        if not file_path or not os.path.exists(file_path):
            self.ui.combobox_teryt_column.clear()
            self.ui.button_start.setEnabled(False)
            return
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                first_line = f.readline()
                f.seek(0)

                potential_seps = [';', '\t', ',', '|']
                sep = next((d for d in potential_seps if d in first_line), ' ')

                reader = csv.reader(f, delimiter=sep)
                self.csv_headers = next(reader)
                self.csv_data = list(reader)

            if self.csv_headers:
                self.ui.combobox_teryt_column.clear()
                self.ui.combobox_teryt_column.addItems(self.csv_headers)
                # Automatyczne wskazywanie kolumny TERYT
                keywords = ['teryt', 'id_teryt', 'kod_teryt']
                for i, header in enumerate(self.csv_headers):
                    if header.lower() in keywords:
                        self.ui.combobox_teryt_column.setCurrentIndex(i)
                        break
                self.ui.button_start.setEnabled(True)
                if not self.parent.dockwidget.radioExistingLayer.isChecked():
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    self.ui.text_edit_layer_name.setText(f"{base_name} - Działki ULDK")
            else:
                raise Exception("Plik CSV wydaje się być pusty.")
        except Exception as e:
            iface.messageBar().pushWidget(QgsMessageBarItem("Wtyczka GIS Support",
                f"Błąd wczytywania pliku: {str(e)}", level=2))
            self.ui.button_start.setEnabled(False)

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
            if self.file_path and os.path.exists(self.file_path):
                base_name = os.path.splitext(os.path.basename(self.file_path))[0]
                self.ui.text_edit_layer_name.setText(f"{base_name} - Działki ULDK")
            else:
                self.ui.text_edit_layer_name.setText("")

    def __handle_found(self, uldk_response_dict: dict[int, list]) -> None:
        current_features = []

        for id_, uldk_response_rows in uldk_response_dict.items():
            for row in uldk_response_rows:
                try:
                    feature = self.result_collector.uldk_response_to_qgs_feature(row, [])
                    current_features.append(feature)
                    self.found_count += 1
                except self.result_collector.BadGeometryException as error:
                    e = self.result_collector.BadGeometryException(error.feature, "Niepoprawna geometria")
                    self._handle_bad_geometry(error.feature, e)
                    self.not_found_count += 1
                    continue
                except self.result_collector.ResponseDataException:
                    e = self.result_collector.ResponseDataException("Błąd przetwarzania danych wynikowych")
                    self._handle_data_error(self.worker.teryt_ids[id_]["teryt"], e)
                    self.not_found_count += 1
                    continue

        if current_features:
            self.result_collector.update_with_features(current_features)
            self.parent.canvas.refresh()

    def __handle_not_found(self, teryt: str, exception: Exception) -> None:
        self._add_table_errors_row(teryt, str(exception))
        self.not_found_count += 1

    def _handle_bad_geometry(self, feature: QgsFeature, exception: Exception) -> None:
        self._add_table_errors_row(feature.attribute("teryt"), str(exception))
        self.not_found_count += 1

    def _handle_data_error(self, teryt: str, exception: Exception) -> None:
        self._add_table_errors_row(teryt, str(exception))
        self.not_found_count += 1

    def __progressed(self) -> None:
        found_count = self.found_count
        not_found_count = self.not_found_count
        progressed_count = found_count + not_found_count
        self.ui.progress_bar.setValue(int(progressed_count/self.csv_rows_count*100))
        self.ui.label_status.setText("Przetworzono {} z {} obiektów".format(progressed_count, self.csv_rows_count))
        self.ui.label_found_count.setText("Znaleziono: {}".format(found_count))
        self.ui.label_not_found_count.setText("Nie znaleziono: {}".format(not_found_count))

    def __handle_finished(self) -> None:
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

        layer_name = self.ui.text_edit_layer_name.text() if self.ui.text_edit_layer_name.text() else "nowa_warstwa"
        iface.messageBar().pushWidget(QgsMessageBarItem("Wtyczka GIS Support",
            f"Wyszukiwanie z pliku CSV: \
                zakończono wyszukiwanie. Zapisano {found_count} {form} \
                    do warstwy <b>{layer_name}</b>"))

        if self.not_found_count > 0:
            self.ui.button_save_not_found.setEnabled(True)

        self.__cleanup_after_search()

    def __handle_interrupted(self) -> None:
        iface.messageBar().pushWidget(QgsMessageBarItem(
            "Wtyczka GIS Support",
            "Wyszukiwanie zostało przerwane przez użytkownika. \
                Obiekty pobrane do tej pory zostały zachowane.",
            level=1))
        self.__cleanup_after_search()

    def _export_table_errors_to_csv(self) -> None:
        count = self.ui.table_errors.rowCount()
        path, _ = QFileDialog.getSaveFileName(filter='*.csv')
        if path:
            with open(path, 'w', encoding='utf-8') as f:
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

    def _add_table_errors_row(self, teryt: str, exception_message: str) -> None:
        row = self.ui.table_errors.rowCount()
        self.ui.table_errors.insertRow(row)
        self.ui.table_errors.setItem(row, 0, QTableWidgetItem(teryt))
        self.ui.table_errors.setItem(row, 1, QTableWidgetItem(exception_message))

    def __cleanup_after_search(self) -> None:
        self.__set_controls_enabled(True)
        self.ui.button_cancel.setText("Anuluj")
        self.ui.button_cancel.setEnabled(False)
        self.ui.progress_bar.setValue(0)

    def __cleanup_before_search(self) -> None:
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
        self.ui.button_start.setEnabled(enabled and self.file_path is not None)

        self.ui.file_select.setEnabled(enabled)
        self.ui.combobox_teryt_column.setEnabled(enabled)

    def __stop(self) -> None:
        self.thread.requestInterruption()
        self.ui.button_cancel.setEnabled(False)
        self.ui.button_cancel.setText("Przerywanie...")
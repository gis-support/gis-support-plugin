import csv
import os

from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QKeySequence, QPixmap
from PyQt5.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem
from qgis.gui import QgsMessageBarItem

from ...uldk import api as uldk_api

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

        self.frame_how_it_works.setToolTip((
            "Narzędzie wyszukuje działki na podstawie listy:\n"
            "załaduj plik CSV, wskaż kolumnę z TERYT i uruchom wyszukiwanie."))   
        self.label_info_icon.setPixmap(QPixmap(self.icon_info_path))

class CSVImport:

    def __init__(self, parent, target_layout, result_collector_factory, layer_factory):
        self.parent = parent
        self.iface = parent.iface
        self.ui = UI(parent.dockwidget, target_layout)

        self.result_collector_factory = result_collector_factory
        self.layer_factory = layer_factory

        self.file_path = None
        
        self.__init_ui()

        self.uldk_search = uldk_api.ULDKSearchParcel("dzialka",
             ("geom_wkt", "wojewodztwo", "powiat", "gmina", "obreb","numer","teryt"))

    def start_import(self):
        self.__cleanup_before_search()

        layer_name = self.ui.text_edit_layer_name.text()
        layer = self.layer_factory(
            name = layer_name, custom_properties = {"ULDK": layer_name})

        self.result_collector = self.result_collector_factory(self.parent, layer)
        self.features_found = []
        
        teryts = []
        with open(self.file_path) as f:
            csv_read = csv.DictReader(f)
            teryt_column = self.ui.combobox_teryt_column.currentText()
            for row in csv_read:
                teryt = row[teryt_column]
                teryts.append(teryt)
        self.csv_rows_count = len(teryts)

        self.worker = uldk_api.ULDKSearchWorker(self.uldk_search, teryts)
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
        
    def __init_ui(self):
        self.ui.button_start.clicked.connect(self.start_import)
        self.ui.label_status.setText("")
        self.ui.label_found_count.setText("")
        self.ui.label_not_found_count.setText("")
        self.ui.button_cancel.clicked.connect(self.__stop)
        self.ui.file_select.fileChanged.connect(self.__on_file_changed)
        self.__init_table()

    def __init_table(self):
        table = self.ui.table_errors
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(("TERYT", "Treść błędu"))
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        teryt_column_size = table.width()/3
        header.resizeSection(0, 200)

    def __on_file_changed(self, path):
        suggested_target_layer_name = ""
        if os.path.exists(path):
            self.ui.button_start.setEnabled(True)
            self.file_path = path
            self.__fill_column_select()
            suggested_target_layer_name = os.path.splitext(os.path.relpath(path))[0]
        else:
            self.file_path = None
            self.ui.combobox_teryt_column.clear()
        self.ui.text_edit_layer_name.setText(suggested_target_layer_name)


    def __fill_column_select(self):
        self.ui.combobox_teryt_column.clear()
        with open(self.file_path) as f:
            csv_read = csv.DictReader(f)
            columns = csv_read.fieldnames
        self.ui.combobox_teryt_column.addItems(columns)
    
    def __handle_found(self, uldk_response_rows):
        for row in uldk_response_rows:
            try:
                feature = self.result_collector.uldk_response_to_qgs_feature(row)
            except self.result_collector.BadGeometryException as e:
                e = self.result_collector.BadGeometryException(e.feature, "Niepoprawna geometria")
                self._handle_bad_geometry(e.feature, e)
                return
            self.features_found.append(feature)
            self.found_count += 1

    def __handle_not_found(self, teryt, exception):
        self._add_table_errors_row(teryt, str(exception))
        self.not_found_count += 1

    def _handle_bad_geometry(self, feature, exception):
        self._add_table_errors_row(feature.attribute("teryt"), str(exception))
        self.not_found_count += 1

    def __progressed(self):
        found_count = self.found_count
        not_found_count = self.not_found_count
        progressed_count = found_count + not_found_count
        self.ui.progress_bar.setValue(progressed_count/self.csv_rows_count*100)
        self.ui.label_status.setText("Przetworzono {} z {} obiektów".format(progressed_count, self.csv_rows_count))
        self.ui.label_found_count.setText("Znaleziono: {}".format(found_count))
        self.ui.label_not_found_count.setText("Nie znaleziono: {}".format(not_found_count))

    def __handle_finished(self):
        self.__collect_received_features()
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

        self.iface.messageBar().pushWidget(QgsMessageBarItem("Wtyczka ULDK",
            f"Import CSV: zakończono wyszukiwanie. Zapisano {found_count} {form} do warstwy <b>{self.ui.text_edit_layer_name.text()}</b>"))
        self.__cleanup_after_search()

    def __handle_interrupted(self):
        self.__collect_received_features()
        self.__cleanup_after_search()

    def __collect_received_features(self):
        if self.features_found:
            self.result_collector.update_with_features(self.features_found)

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
        self.ui.table_errors.setRowCount(0)
        self.ui.label_status.setText("")
        self.ui.label_found_count.setText("")
        self.ui.label_not_found_count.setText("")

        self.found_count = 0
        self.not_found_count = 0

    def __set_controls_enabled(self, enabled):
        self.ui.text_edit_layer_name.setEnabled(enabled)
        self.ui.button_start.setEnabled(enabled)
        self.ui.file_select.setEnabled(enabled)
        self.ui.combobox_teryt_column.setEnabled(enabled)

    def __stop(self):
        self.thread.requestInterruption()
        self.ui.button_cancel.setEnabled(False)
        self.ui.button_cancel.setText("Przerywanie...")

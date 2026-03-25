import json

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QFileDialog
from qgis.gui import QgsMessageBarItem
from qgis.core import QgsApplication, Qgis, QgsGeometry, QgsCoordinateReferenceSystem, QgsVectorLayer, QgsWkbTypes, QgsProject
from qgis.utils import iface

from gissupport_plugin.modules.data_downloader.prg_address.prg_address_dockwidget import PRGAddressDockWidget
from gissupport_plugin.modules.data_downloader.prg_address.utils import PRGAddressDownloadTask, \
    transform_geometry_to_2180, convert_multi_polygon_to_polygon, PRGAddressDataBoxDownloadTask
from gissupport_plugin.tools.teryt import Wojewodztwa, POWIATY


class PRGAddressDownloader:
    def __init__(self):
        self.task = None

        self.teryt_w = ""
        self.teryt_p = ""
        self.layer_name = "PRG - punkty adresowe"

        self.selected_geometry = QgsGeometry()
        self.databox_layers = None
        self.drawpolygon = None
        self.drawrectangle = None
        self.current_layer = None

        self.prg_address_dockwidget = None
        self.init_prg_address_dockwidget()

    def init_prg_address_dockwidget(self):
        self.prg_address_dockwidget = PRGAddressDockWidget()
        iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.prg_address_dockwidget)
        self.prg_address_dockwidget.hide()

        self.fill_combobox_w()
        self.fill_combobox_p()

        ### POBIERANIE DLA WYBRANEGO POWIATU
        self.prg_address_dockwidget.browseButton.clicked.connect(self.browse_filepath_for_prg_address)
        self.prg_address_dockwidget.wComboBox.currentTextChanged.connect(self.fill_combobox_p)
        self.prg_address_dockwidget.pComboBox.currentTextChanged.connect(self.get_teryt_pow)
        self.prg_address_dockwidget.pDownloadBtn.clicked.connect(self.download_prg_address)

        ### POBIERANIE DLA ZASIĘGU
        self.select_features_rectangle_tool_prg = self.prg_address_dockwidget.gsSelectAreaWidget.select_features_rectangle_tool
        self.select_features_freehand_tool_prg = self.prg_address_dockwidget.gsSelectAreaWidget.select_features_freehand_tool
        self.select_features_tool_prg = self.prg_address_dockwidget.gsSelectAreaWidget.select_features_tool

        self.select_features_rectangle_tool_prg.geometryEnded.connect(self.set_geometry_from_draw)
        self.select_features_freehand_tool_prg.geometryEnded.connect(self.set_geometry_from_draw)
        self.select_features_tool_prg.geometryEnded.connect(self.set_geometry_from_draw)

        self.prg_address_dockwidget.boundsDownloadBtn.clicked.connect(self.download_prg_address_from_databox)
        self.prg_address_dockwidget.boundsDownloadBtn.setEnabled(False)


    def change_prg_address_dockwidget_visibility(self):
        """
        Zmienia widoczność widgetu `PRG - punkty adresowe` przy wyborze z menu. Inicjuje widget przy pierwszym uruchomieniu.
        """
        if self.prg_address_dockwidget is None:
            self.init_prg_address_dockwidget()
        self.prg_address_dockwidget.setVisible(not self.prg_address_dockwidget.isVisible())


    ### POBIERANIE DLA WYBRANEGO POWIATU
    def fill_combobox_w(self):
        """
        Uzupełnia combobox z województwami. Wywoływane raz, przy starcie pluginu.
        """
        wojewodztwa = [woj.value for woj in Wojewodztwa]
        self.prg_address_dockwidget.wComboBox.clear()
        for item in wojewodztwa:
            self.prg_address_dockwidget.wComboBox.addItem(item)
        self.teryt_w = wojewodztwa[0].split("|")[1].strip()

    def fill_combobox_p(self):
        """
        Uzupelnia combobox z powiatami, na podstawie wybranego województwa.
        Wywoływane po wyborze województwa.
        """
        current_woj = self.prg_address_dockwidget.wComboBox.currentText()
        self.teryt_w = current_woj.split("|")[1].strip() if current_woj else ""
        powiaty = POWIATY.get(Wojewodztwa(current_woj), [])
        self.prg_address_dockwidget.pComboBox.clear()
        for powiat in powiaty:
            self.prg_address_dockwidget.pComboBox.addItem(powiat)
        self.teryt_p = powiaty[0].split("|")[1].strip()

    def get_teryt_pow(self):
        """
        Zapisuje teryt wybranego powiatu z comboboxa.
        """
        current_pow = self.prg_address_dockwidget.pComboBox.currentText()
        self.teryt_p = current_pow.split("|")[1].strip() if current_pow else ""

    def browse_filepath_for_prg_address(self):
        """
        Uruchamia okno z wyborem miejsca zapisu plików `PRG - punkty adresowe` i zapisuje ścieżkę.
        """
        prg_address_filepath = QFileDialog.getExistingDirectory(self.prg_address_dockwidget,
                                                 'Wybierz miejsce zapisu punktów adresowych PRG')
        self.prg_address_dockwidget.filePathLineEdit.setText(prg_address_filepath)

    def download_prg_address(self):
        """
        Uruchamia pobieranie danych.
        """
        if self.teryt_w == "" or self.teryt_p == "":
            iface.messageBar().pushMessage("Przed pobraniem należy wybrać województwo i powiat",
                                           level=Qgis.MessageLevel.Warning)
            return

        prg_address_filepath = self.prg_address_dockwidget.filePathLineEdit.text()
        if not prg_address_filepath or prg_address_filepath == "":
            iface.messageBar().pushMessage("Przed pobraniem należy wybrać ścieżkę zapisu danych",
                                           level=Qgis.MessageLevel.Warning)
            return

        self.task = PRGAddressDownloadTask("Pobieranie punktów adresowych PRG",
                                        teryt_p=self.teryt_p, filepath=prg_address_filepath)
        self.task.progress_updated.connect(self.update_prg_address_download_progress)
        self.task.download_finished.connect(self.show_prg_address_success_message)
        self.task.task_failed.connect(self.handle_prg_address_task_error)

        manager = QgsApplication.taskManager()
        manager.addTask(self.task)

        self.select_features_tool_prg.deactivate()
        self.select_features_freehand_tool_prg.deactivate()
        self.select_features_rectangle_tool_prg.deactivate()

    def update_prg_address_download_progress(self, value: int):
        """
        Aktualizuje pasek postępu pobierania danych.
        """
        self.task.setProgress(value)

    def show_prg_address_success_message(self):
        """
        Wyświetla komunikat o pomyślnym pobraniu danych.
        """
        iface.messageBar().pushWidget(QgsMessageBarItem("Wtyczka GIS Support",
                    "Pomyślnie pobrano dane PRG - punkty adresowe", level=Qgis.MessageLevel.Info))

    def handle_prg_address_task_error(self, error_message):
        iface.messageBar().pushMessage("Wtyczka GIS Support", error_message, level=Qgis.MessageLevel.Critical)

    ### POBIEARNIE DLA ZASIĘGU
    def set_geometry_from_draw(self, area: float, geom: QgsGeometry):
        self.selected_geometry = geom
        if not self.selected_geometry.isNull():
            self.prg_address_dockwidget.boundsDownloadBtn.setEnabled(True)

    def on_select_method_changed(self):
        self.select_features_rectangle_tool_prg.reset_geometry()
        self.select_features_freehand_tool_prg.reset_geometry()
        self.select_features_tool_prg.reset_geometry()
        self.selected_geometry = None

    def on_layer_changed(self):
        self.set_geometry_for_selection()

    def set_geometry_for_selection(self):
        selected_layer = self.prg_address_dockwidget.gsSelectAreaWidget.selectLayerCb.currentLayer()

        if selected_layer:
            if self.prg_address_dockwidget.gsSelectAreaWidget.selectLayerFeatsCb.isChecked():
                selected_features = selected_layer.getSelectedFeatures()
            else:
                selected_features = selected_layer.getFeatures()

            geom = QgsGeometry.unaryUnion([f.geometry() for f in selected_features])
            crs_src = selected_layer.crs()
            if crs_src != QgsCoordinateReferenceSystem.fromEpsgId(2180):
                self.selected_geometry = transform_geometry_to_2180(geom, crs_src)
            else:
                self.selected_geometry = geom

    def download_prg_address_from_databox(self):
        if self.prg_address_dockwidget.gsSelectAreaWidget.selectMethodCb.currentText() == 'Wskaż obiekty':
            self.set_geometry_for_selection()
        else:
            if self.selected_geometry.isMultipart():
                self.selected_geometry = convert_multi_polygon_to_polygon(self.selected_geometry)


        self.task = PRGAddressDataBoxDownloadTask("Pobieranie danych punktów adresowych PRG", self.layer_name, self.selected_geometry)
        self.task.downloaded_data.connect(self.add_prg_address_features_to_map)
        self.task.downloaded_details.connect(self.show_prg_address_databox_limit_exceeded_message)
        manager = QgsApplication.taskManager()
        manager.addTask(self.task)

        self.select_features_tool_prg.deactivate()
        self.select_features_freehand_tool_prg.deactivate()
        self.select_features_rectangle_tool_prg.deactivate()

    def show_prg_address_databox_limit_exceeded_message(self, message: str):
        iface.messageBar().pushMessage(message, level=Qgis.MessageLevel.Warning)

    def add_prg_address_features_to_map(self, geojson: str):
        existing_layer = QgsProject.instance().mapLayersByName(self.layer_name)

        geojson_layer = QgsVectorLayer(geojson, "temp", "ogr")
        if geojson_layer.featureCount() <= 0:
            self.show_prg_address_databox_error_message()
            return

        else:
            if existing_layer:
                layer = existing_layer[0]
                geojson_layer = QgsVectorLayer(geojson, "temp", "ogr")
                new_features = geojson_layer.getFeatures()
                layer.startEditing()
                layer.addFeatures(new_features)
                layer.commitChanges()

            else:
                # warstwa z geojsona z data box jest read only, tworzymy nową warstwę którą można edytować
                geojson_layer = QgsVectorLayer(geojson, "temp", "ogr")
                fields = geojson_layer.fields()
                geom_type_str = QgsWkbTypes.displayString(geojson_layer.wkbType())
                uri = f"{geom_type_str}?crs=EPSG:2180"
                layer = QgsVectorLayer(uri, self.layer_name, "memory")

                provider = layer.dataProvider()
                provider.addAttributes(fields)

                layer.updateFields()
                layer.startEditing()
                layer.addFeatures(geojson_layer.getFeatures())
                layer.commitChanges()

                QgsProject.instance().addMapLayer(layer)

            self.show_prg_address_success_message()

    def show_prg_address_databox_error_message(self):
        """
        Wyświetla komunikat o błędzie pobierania danych `PRG - punkty adresowe` z DataBox.
        """
        iface.messageBar().pushMessage("Wtyczka GIS Support",
                                       """Na wybranym obszarze nie znajdują się obiekty wybranej warstwy
                                       lub liczba obiektów na wybranym obszarze jest większa niż 100 000""",
                                       level=Qgis.MessageLevel.Warning)


from typing import List, Union
from os.path import expanduser

from qgis._core import QgsCoordinateReferenceSystem
from qgis.core import Qgis, QgsApplication, QgsVectorLayer, QgsProject, QgsMapLayerProxyModel, QgsGeometry, QgsWkbTypes, QgsMessageLog
from qgis.gui import QgsMessageBarItem, QgsMapTool
from qgis.utils import iface
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QFileDialog, QPushButton

from gissupport_plugin.modules.data_downloader.bdot10k.bdot10k_dockwidget import BDOT10kDockWidget
from gissupport_plugin.modules.data_downloader.bdot10k.utils import BDOT10kDownloadTask, DrawPolygon, \
    get_databox_layers, BDOT10kDataBoxDownloadTask, convert_multi_polygon_to_polygon, transform_geometry_to_2180, \
    BDOT10kClassDownloadTask, DataboxResponseException, check_geoportal_connection, GeoportalResponseException
from gissupport_plugin.modules.gis_box.modules.auto_digitization.tools import SelectRectangleTool
from gissupport_plugin.tools.teryt import Wojewodztwa, POWIATY

class BDOT10kDownloader:

    def __init__(self):
        self.task = None
        self.bdot10k_class_filepath = expanduser("~")
        self.teryt_woj = ""
        self.teryt_pow = ""
        self.bdot10k_class = ""

        self.bdot10k_dockwidget = None
        self.selected_geom = QgsGeometry()
        self.databox_layers = None
        self.current_layer = None

    def init_bdot10k_dockwidget(self):
        self.bdot10k_dockwidget = BDOT10kDockWidget()
        # Zapobiega usunięciu obiektu przez Garbage Collector
        self.bdot10k_dockwidget._controller = self 
        
        iface.addDockWidget(Qt.RightDockWidgetArea, self.bdot10k_dockwidget)
        self.bdot10k_dockwidget.hide()

        self.fill_woj_combobox()
        self.fill_pow_combobox()
    
        self.bdot10k_dockwidget.browseButton.clicked.connect(self.browse_filepath_for_bdot10k)
        self.bdot10k_dockwidget.wojComboBox.currentTextChanged.connect(self.fill_pow_combobox)
        self.bdot10k_dockwidget.powComboBox.currentTextChanged.connect(self.get_teryt_pow)
        self.bdot10k_dockwidget.downloadButton.clicked.connect(self.download_bdot10k)
        self.bdot10k_dockwidget.downloadButton.setEnabled(False)
        self.bdot10k_dockwidget.filepathLine.textChanged.connect(lambda text: self.set_powiat_class_button_state(text, self.bdot10k_dockwidget.downloadButton))

        # Podłączenie sygnału z widgetu zaznaczania
        self.bdot10k_dockwidget.selectAreaWidget.geometryCreated.connect(self.set_geometry_from_signal)

        self.bdot10k_dockwidget.selectAreaWidget.methodChanged.connect(self.on_select_method_changed)
        self.bdot10k_dockwidget.selectAreaWidget.selectLayerCb.layerChanged.connect(self.on_layer_changed)

        self.bdot10k_dockwidget.boundsDownloadButton.clicked.connect(self.download_bdot10k_from_databox)
        self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(False)

        self.bdot10k_dockwidget.classBrowseButton.clicked.connect(self.browse_filepath_for_class_bdot10k)
        self.bdot10k_dockwidget.classDownloadButton.clicked.connect(self.download_class_bdot10k)
        self.bdot10k_dockwidget.classDownloadButton.setEnabled(False)
        self.bdot10k_dockwidget.classComboBox.currentTextChanged.connect(self.get_class)
        self.bdot10k_dockwidget.classFilePathLine.textChanged.connect(lambda text: self.set_powiat_class_button_state(text, self.bdot10k_dockwidget.classDownloadButton))

        try:
            check_geoportal_connection()
        except GeoportalResponseException as e:
            self.bdot10k_dockwidget.powiat.setEnabled(False)
            iface.messageBar().pushMessage("Wtyczka GIS Support", f"Błąd połączenia z Geoportalem: {e}", level=Qgis.Critical)

        try:
            self.databox_layers = get_databox_layers()
        except DataboxResponseException as e:
            self.bdot10k_dockwidget.bounds.setEnabled(False)
            self.bdot10k_dockwidget.classTab.setEnabled(False)
            iface.messageBar().pushMessage("Wtyczka GIS Support", f"Błąd połączenia z Databox: {e}",
                                           level=Qgis.Critical)
            return

        self.fill_class_combobox()
        self.bdot10k_dockwidget.layerComboBox.addItems(list(self.databox_layers.keys()))



    def set_powiat_class_button_state(self, text: str, button: QPushButton):
        """
        Zmienia status przycisku w zależności czy podano ścieżkę do zapisu plików.
        Tylko dla zakładek `Dla powiatu` i `Dla klasy`.
        """
        if text and len(text) > 0:
            button.setEnabled(True)
        else:
            button.setEnabled(False)

        self.bdot10k_dockwidget.selectAreaWidget.selectLayerCb.layerChanged.connect(self.on_layer_changed)

### pobieranie dla wybranego powiatu
    def browse_filepath_for_bdot10k(self):
        """
        Uruchamia okno z wyborem miejsca zapisu plików BDOT10k i zapisuje ścieżkę.
        """
        bdot10k_filepath = QFileDialog.getExistingDirectory(self.bdot10k_dockwidget,
                                                 'Wybierz miejsce zapisu plików BDOT10k')
        self.bdot10k_dockwidget.filepathLine.setText(bdot10k_filepath)

    def change_bdot10k_dockwidget_visibility(self):
        """
        Zmienia widoczność widgetu BDOT10k przy wyborze z menu. Inicjuje widget przy pierwszym uruchomieniu.
        """
        if self.bdot10k_dockwidget is None:
            self.init_bdot10k_dockwidget()
       
        self.bdot10k_dockwidget.setVisible(not self.bdot10k_dockwidget.isVisible())

    def fill_woj_combobox(self):
        """
        Uzupełnia combobox z województwami. Wywoływane raz, przy starcie pluginu.
        """
        wojewodztwa = [woj.value for woj in Wojewodztwa]
        self.bdot10k_dockwidget.wojComboBox.clear()
        for item in wojewodztwa:
            self.bdot10k_dockwidget.wojComboBox.addItem(item)
        self.teryt_woj = wojewodztwa[0].split("|")[1].strip()

    def fill_pow_combobox(self):
        """
        Uzupelnia combobox z powiatami, na podstawie wybranego województwa.
        Wywoływane po wyborze województwa.
        """
        current_woj = self.bdot10k_dockwidget.wojComboBox.currentText()
        self.teryt_woj = current_woj.split("|")[1].strip() if current_woj else ""
        powiaty = POWIATY.get(Wojewodztwa(current_woj), [])
        self.bdot10k_dockwidget.powComboBox.clear()
        for powiat in powiaty:
            self.bdot10k_dockwidget.powComboBox.addItem(powiat)
        self.teryt_pow = powiaty[0].split("|")[1].strip()

    def get_teryt_pow(self):
        """
        Zapisuje teryt wybranego powiatu z comboboxa.
        """
        current_pow = self.bdot10k_dockwidget.powComboBox.currentText()
        self.teryt_pow = current_pow.split("|")[1].strip() if current_pow else ""

    def download_bdot10k(self):
        """
        Uruchamia pobieranie danych BDOT10k.
        """
        if self.teryt_woj == "" or self.teryt_pow == "":
            iface.messageBar().pushMessage("Przed pobraniem należy wybrać województwo i powiat",
                                           level=Qgis.Warning)
            return

        bdot10k_filepath = self.bdot10k_dockwidget.filepathLine.text()
        if not bdot10k_filepath or bdot10k_filepath == "":
            iface.messageBar().pushMessage("Przed pobraniem należy wybrać ścieżkę zapisu danych",
                                           level=Qgis.Warning)
            return

        self.task = BDOT10kDownloadTask("Pobieranie danych BDOT10k", self.teryt_woj,
                                        self.teryt_pow, bdot10k_filepath)
        self.task.progress_updated.connect(self.update_bdok10k_download_progress)
        self.task.download_finished.connect(self.show_bdot10k_success_message)
        self.task.task_failed.connect(self.handle_task_error)

        manager = QgsApplication.taskManager()
        manager.addTask(self.task)
        

    def update_bdok10k_download_progress(self, value: int):
        """
        Aktualizuje pasek postępu pobierania danych BDOT10k.
        """
        self.task.setProgress(value)

    def show_bdot10k_success_message(self):
        """
        Wyświetla komunikat o pomyślnym pobraniu danych BDOT10k.
        """
        iface.messageBar().pushWidget(QgsMessageBarItem("Wtyczka GIS Support",
                    "Pomyślnie pobrano dane BDOT10k", level=Qgis.Info))

    def set_geometry_from_signal(self, geom):
        """Odbiera geometrię z sygnału widgetu GsSelectArea"""
        if geom and not geom.isNull():
            try:
                # domyslnie uklad mapy dla narzedzi rysowania
                crs_src = iface.mapCanvas().mapSettings().destinationCrs()

                widget = self.bdot10k_dockwidget.selectAreaWidget
                if widget.selectMethodCb.currentText() == 'Wskaz obiekty':
                    layer = widget.selectLayerCb.currentLayer()
                    if layer and layer.isValid():
                        # crs z warstwy, nie z mapy
                        crs_src = layer.crs()

                if crs_src != QgsCoordinateReferenceSystem.fromEpsgId(2180):
                        self.selected_geom = transform_geometry_to_2180(QgsGeometry(geom), crs_src)
                else:
                        self.selected_geom = QgsGeometry(geom)
                
                self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(True)
            except (ValueError, TypeError, RuntimeError) as e:
                QgsMessageLog.logMessage(f"Błąd przetwarzania geometrii: {e}", "Wtyczka GIS Support", Qgis.Warning)
                self.selected_geom = None
                self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(False)
        else:
            self.selected_geom = None
            self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(False)

    def on_select_method_changed(self):
        self.selected_geom = None
        self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(False)

    def on_layer_changed(self):
        if self.current_layer:
            try:
                self.current_layer.selectionChanged.disconnect(self.on_layer_selection_changed_handler)
            except: 
                pass

        new_layer = self.bdot10k_dockwidget.selectAreaWidget.selectLayerCb.currentLayer()
        if new_layer:
            self.current_layer = new_layer
            self.current_layer.selectionChanged

    def set_geometry_for_selection(self):
        selected_layer = self.bdot10k_dockwidget.selectAreaWidget.selectLayerCb.currentLayer()

        if selected_layer:
            if self.bdot10k_dockwidget.selectAreaWidget.selectLayerFeatsCb.isChecked():
                selected_features = selected_layer.getSelectedFeatures()
            else:
                selected_features = selected_layer.getFeatures()

            #Zabezpieczenie listy
            feats_list = [f for f in selected_features]
            if not feats_list:
                self.selected_geom = None
                self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(False)
                return

            geom = QgsGeometry.unaryUnion([f.geometry() for f in feats_list])
            crs_src = selected_layer.crs()
            if crs_src != QgsCoordinateReferenceSystem.fromEpsgId(2180):
                self.selected_geom = transform_geometry_to_2180(geom, crs_src)
            else:
                self.selected_geom = geom
            
            #Włączenie przycisku jeśli geometria jest OK
            if not self.selected_geom.isNull():
                 self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(True)
            else:
                 self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(False)


    def download_bdot10k_from_databox(self):
        if self.bdot10k_dockwidget.selectAreaWidget.selectMethodCb.currentText() == 'Wskaż obiekty':
            self.set_geometry_for_selection()
        else:
            if self.selected_geom and self.selected_geom.isMultipart():
                self.selected_geom = convert_multi_polygon_to_polygon(self.selected_geom)

        layer_name = self.bdot10k_dockwidget.layerComboBox.currentText()
        layer_name = self.databox_layers.get(layer_name)
        
        #Używamy self.selected_geom, który został ustawiony wcześniej
        self.task = BDOT10kDataBoxDownloadTask("Pobieranie danych BDOT10k", layer_name, self.selected_geom)
        self.task.downloaded_data.connect(self.add_bdot10k_features_to_map)
        self.task.downloaded_details.connect(self.show_bdot10k_databox_limit_exceeded_message)
        manager = QgsApplication.taskManager()
        manager.addTask(self.task)

    def show_bdot10k_databox_limit_exceeded_message(self, message: str):
        iface.messageBar().pushMessage(message, level=Qgis.Warning)
    
    def add_bdot10k_features_to_map(self, geojson: str):
        layer_name = self.bdot10k_dockwidget.layerComboBox.currentText()
        existing_layer = QgsProject.instance().mapLayersByName(layer_name)

        geojson_layer = QgsVectorLayer(geojson, "temp", "ogr")
        if not geojson_layer.isValid() or geojson_layer.featureCount() <= 0 :
            self.show_bdot10k_databox_error_message()
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
                layer = QgsVectorLayer(uri, layer_name, "memory")

                provider = layer.dataProvider()
                provider.addAttributes(fields)

                layer.updateFields()
                layer.startEditing()
                layer.addFeatures(geojson_layer.getFeatures())
                layer.commitChanges()

                QgsProject.instance().addMapLayer(layer)

            self.show_bdot10k_success_message()

    def show_bdot10k_databox_error_message(self):
        """
        Wyświetla komunikat o błędzie pobierania danych BDOT10k z DataBox.
        """
        iface.messageBar().pushMessage("Wtyczka GIS Support",
                    """Na wybranym obszarze nie znajdują się obiekty wybranej warstwy
                    lub liczba obiektów na wybranym obszarze jest większa niż 100 000""", level=Qgis.Warning)

### POBIERANIE DLA KLASY

    def fill_class_combobox(self):
        """
        Uzupełnia combobox z klasami. Wywoływane raz, przy starcie pluginu.
        """
        classes = self.databox_layers
        self.bdot10k_dockwidget.classComboBox.clear()
        for item in classes.items():
            display_name = f'{item[0]}'
            self.bdot10k_dockwidget.classComboBox.addItem(display_name, item[1])

    def browse_filepath_for_class_bdot10k(self):
        """
        Uruchamia okno z wyborem miejsca zapisu plików BDOT10k i zapisuje ścieżkę.
        """
        self.bdot10k_class_filepath = QFileDialog.getExistingDirectory(self.bdot10k_dockwidget,
                                                 'Wybierz miejsce zapisu plików BDOT10k',
                                                 expanduser("~"))
        self.bdot10k_dockwidget.classFilePathLine.setText(self.bdot10k_class_filepath)

    def download_class_bdot10k(self):
        """
        Uruchamia pobieranie danych BDOT10k.
        """
        if self.bdot10k_class == "":
            iface.messageBar().pushMessage("Przed pobraniem należy wybrać klasę BDOT10k",
                                           level=Qgis.Warning)
            return

        self.task = BDOT10kClassDownloadTask("Pobieranie danych BDOT10k dla wybranej klasy",
                                             self.bdot10k_class, self.bdot10k_class_filepath)
        self.task.progress_updated.connect(self.update_bdok10k_download_progress)
        self.task.download_finished.connect(self.show_bdot10k_success_message)

        manager = QgsApplication.taskManager()
        manager.addTask(self.task)

    def get_class(self):
        """
        Zapisuje teryt wybranego powiatu z comboboxa.
        """
        current_class = self.bdot10k_dockwidget.classComboBox.currentData()
        self.bdot10k_class = str(current_class).upper()

    def handle_task_error(self, error_message):
        iface.messageBar().pushMessage("Wtyczka GIS Support", error_message, level=Qgis.Critical)

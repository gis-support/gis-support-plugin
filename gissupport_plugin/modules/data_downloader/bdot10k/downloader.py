from typing import List, Union
from os.path import expanduser

from qgis.core import Qgis, QgsApplication, QgsVectorLayer, QgsProject, QgsMapLayerProxyModel, QgsGeometry, QgsWkbTypes
from qgis.gui import QgsMessageBarItem, QgsMapTool
from qgis.utils import iface
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QFileDialog

from gissupport_plugin.modules.data_downloader.bdot10k.bdot10k_dockwidget import BDOT10kDockWidget
from gissupport_plugin.modules.data_downloader.bdot10k.utils import BDOT10kDownloadTask, DrawPolygon, \
    get_databox_layers, BDOT10kDataBoxDownloadTask, convert_multi_polygon_to_polygon, transform_geometry_to_2180, \
    BDOT10kClassDownloadTask, DataboxResponseException
from gissupport_plugin.modules.uldk.uldk.api import ULDKSearchTeryt, RequestException
from gissupport_plugin.modules.gis_box.modules.auto_digitization.tools import SelectRectangleTool


class BDOT10kDownloader:

    def __init__(self):
        self.task = None
        self.bdot10k_filepath = expanduser("~")
        self.bdot10k_class_filepath = expanduser("~")
        self.teryt_woj = ""
        self.teryt_pow = ""
        self.bdot10k_class = ""

        self.bdot10k_dockwidget = None
        self.selected_geom = QgsGeometry()
        self.databox_layers = None
        self.drawpolygon = None
        self.drawrectangle = None
        self.current_layer = None

    def init_bdot10k_dockwidget(self):

        self.bdot10k_dockwidget = BDOT10kDockWidget()

        try:
            self.fill_woj_combobox()
        except RequestException as e:
            self.bdot10k_dockwidget.powiat.setEnabled(False)
            iface.messageBar().pushMessage("Wtyczka GIS Support", f"Błąd połączenia z ULDK: {e}",
                                           level=Qgis.Critical)
        else:
            self.bdot10k_dockwidget.browseButton.clicked.connect(self.browse_filepath_for_bdot10k)
            self.bdot10k_dockwidget.wojComboBox.currentTextChanged.connect(self.fill_pow_combobox)
            self.bdot10k_dockwidget.powComboBox.currentTextChanged.connect(self.get_teryt_pow)
            self.bdot10k_dockwidget.downloadButton.clicked.connect(self.download_bdot10k)
        
        try:
            self.databox_layers = get_databox_layers()
        except DataboxResponseException as e:
            self.bdot10k_dockwidget.bounds.setEnabled(False)
            self.bdot10k_dockwidget.classTab.setEnabled(False)
            iface.messageBar().pushMessage("Wtyczka GIS Support", f"Błąd połączenia z Databox: {e}",
                                           level=Qgis.Critical)
        else:
            self.fill_class_combobox()

            self.bdot10k_dockwidget.methodComboBox.addItems(['Prostokątem', 'Swobodnie', 'Wskaż obiekty'])
            self.bdot10k_dockwidget.methodComboBox.currentTextChanged.connect(self.change_selection_method)

            self.drawpolygon = DrawPolygon(self.bdot10k_dockwidget)
            self.drawrectangle = SelectRectangleTool(self.bdot10k_dockwidget)
            self.drawrectangle.setButton(self.bdot10k_dockwidget.drawBoundsButton)
            self.bdot10k_dockwidget.drawBoundsButton.clicked.connect(lambda: self.activateTool(self.drawrectangle))
            self.drawpolygon.selectionDone.connect(self.set_geometry_from_draw)
            self.drawrectangle.geometryEnded.connect(lambda area, geometry: self.set_geometry_from_draw(geometry))

            self.bdot10k_dockwidget.layerComboBox.addItems(list(self.databox_layers.keys()))
            self.bdot10k_dockwidget.boundsDownloadButton.clicked.connect(self.download_bdot10k_from_databox)
            self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(False)

            self.bdot10k_dockwidget.fromLayerComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
            self.bdot10k_dockwidget.fromLayerComboBox.hide()
            self.bdot10k_dockwidget.fromLayerLabel.hide()
            self.bdot10k_dockwidget.fromLayerComboBox.layerChanged.connect(self.set_download_button_state)

            self.bdot10k_dockwidget.classBrowseButton.clicked.connect(self.browse_filepath_for_class_bdot10k)
            self.bdot10k_dockwidget.classDownloadButton.clicked.connect(self.download_class_bdot10k)
            self.bdot10k_dockwidget.classComboBox.currentTextChanged.connect(self.get_class)

### pobieranie dla wybranego powiatu
    def browse_filepath_for_bdot10k(self):
        """
        Uruchamia okno z wyborem miejsca zapisu plików BDOT10k i zapisuje ścieżkę.
        """
        self.bdot10k_filepath = QFileDialog.getExistingDirectory(self.bdot10k_dockwidget,
                                                 'Wybierz miejsce zapisu plików BDOT10k',
                                                 expanduser("~"))
        self.bdot10k_dockwidget.filepathLine.setText(self.bdot10k_filepath)

    def change_bdot10k_dockwidget_visibility(self):
        """
        Zmienia widoczność widgetu BDOT10k przy wyborze z menu. Inicjuje widget przy pierwszym uruchomieniu.
        """
        if self.bdot10k_dockwidget is None:
            self.init_bdot10k_dockwidget()
        if not self.bdot10k_dockwidget.isVisible():
            iface.addDockWidget(Qt.RightDockWidgetArea, self.bdot10k_dockwidget)
        else:
            iface.removeDockWidget(self.bdot10k_dockwidget)

    def fill_woj_combobox(self):
        """
        Uzupełnia combobox z województwami. Wywoływane raz, przy starcie pluginu.
        """
        wojewodztwa = self.get_administratives_bdot10k("wojewodztwo")
        self.bdot10k_dockwidget.wojComboBox.clear()
        self.bdot10k_dockwidget.wojComboBox.addItem("")
        for item in wojewodztwa:
            display_name = f'{item[0]} | {item[1]}'
            self.bdot10k_dockwidget.wojComboBox.addItem(display_name, item[1])

    def fill_pow_combobox(self):
        """
        Uzupelnia combobox z powiatami, na podstawie wybranego województwa.
        Wywoływane po wyborze województwa.
        """
        current_woj = self.bdot10k_dockwidget.wojComboBox.currentText()
        self.teryt_woj = current_woj.split("|")[1].strip() if current_woj else ""
        powiaty = self.get_administratives_bdot10k("powiat", self.teryt_woj)
        self.bdot10k_dockwidget.powComboBox.clear()
        self.bdot10k_dockwidget.powComboBox.addItem("")
        for powiat in powiaty:
            display_name = f'{powiat[0]} | {powiat[1]}'
            self.bdot10k_dockwidget.powComboBox.addItem(display_name, powiat[1])

    def get_administratives_bdot10k(self, level: str, teryt: str = ""):
        """
        Pobiera dane (województwa, powiaty, gminy) dla comboboxów.
        """
        search = ULDKSearchTeryt(level, ("nazwa", "teryt"))
        result = search.search(teryt)
        result = [r.split("|") for r in result]

        return result

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

        self.task = BDOT10kDownloadTask("Pobieranie danych BDOT10k", self.teryt_woj,
                                        self.teryt_pow, self.bdot10k_filepath)
        self.task.progress_updated.connect(self.update_bdok10k_download_progress)
        self.task.download_finished.connect(self.show_bdot10k_success_message)

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

### pobieranie dla zasięgu
    def change_selection_method(self):

        self.drawpolygon.deactivate()
        self.drawrectangle.deactivate()

        if self.bdot10k_dockwidget.methodComboBox.currentText() == 'Wskaż obiekty':
            self.bdot10k_dockwidget.fromLayerLabel.show()
            self.bdot10k_dockwidget.fromLayerComboBox.show()
            self.bdot10k_dockwidget.drawBoundsButton.hide()
            self.set_download_button_state()

        else:
            self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(False)
            self.bdot10k_dockwidget.drawBoundsButton.clicked.disconnect()
            self.bdot10k_dockwidget.drawBoundsButton.show()

            if self.bdot10k_dockwidget.methodComboBox.currentText() == 'Swobodnie':
                self.drawpolygon.setButton(self.bdot10k_dockwidget.drawBoundsButton)
                self.bdot10k_dockwidget.drawBoundsButton.clicked.connect(lambda: self.activateTool(self.drawpolygon))

            elif self.bdot10k_dockwidget.methodComboBox.currentText() == 'Prostokątem':
                self.drawrectangle.setButton(self.bdot10k_dockwidget.drawBoundsButton)
                self.bdot10k_dockwidget.drawBoundsButton.clicked.connect(lambda: self.activateTool(self.drawrectangle))

            self.bdot10k_dockwidget.fromLayerLabel.hide()
            self.bdot10k_dockwidget.fromLayerComboBox.hide()
    
    def set_download_button_state(self):
        if self.current_layer:
            self.current_layer.selectionChanged.disconnect(self.on_selection_change)
        selected_layer = self.bdot10k_dockwidget.fromLayerComboBox.currentLayer()
        if selected_layer:
            self.current_layer = selected_layer
            selected_layer.selectionChanged.connect(self.on_selection_change)
            self.on_selection_change(selected_layer.selectedFeatureCount())
        else:
            self.current_layer = None
            self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(False)

    def on_selection_change(self, selected_feature_count: Union[int, List[int]]):
        selected_feature_count = len(selected_feature_count) if isinstance(selected_feature_count, list) else selected_feature_count
        self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(selected_feature_count > 0)

    def set_geometry_from_draw(self, geom: QgsGeometry):
        self.selected_geom = geom
        if not self.selected_geom.isNull():
            self.bdot10k_dockwidget.boundsDownloadButton.setEnabled(True)

    def set_geometry_for_selection(self):
        selected_layer = self.bdot10k_dockwidget.fromLayerComboBox.currentLayer()
        if selected_layer:
            selected_features = selected_layer.getSelectedFeatures()
            geom = QgsGeometry.unaryUnion([f.geometry() for f in selected_features])
            crs_src = selected_layer.crs()
            self.selected_geom  = transform_geometry_to_2180(geom, crs_src)

    def activateTool(self, tool: QgsMapTool):
        iface.mapCanvas().setMapTool(tool)

    def download_bdot10k_from_databox(self):
        if self.bdot10k_dockwidget.methodComboBox.currentText() == 'Wskaż obiekty':
            self.set_geometry_for_selection()
        else:
            if self.selected_geom.isMultipart():
                self.selected_geom = convert_multi_polygon_to_polygon(self.selected_geom)

        layer_name = self.bdot10k_dockwidget.layerComboBox.currentText()
        layer_name = self.databox_layers.get(layer_name)
        self.task = BDOT10kDataBoxDownloadTask("Pobieranie danych BDOT10k", layer_name, self.selected_geom)
        self.task.downloaded_data.connect(self.add_features_to_map)
        manager = QgsApplication.taskManager()
        manager.addTask(self.task)
    
    def add_features_to_map(self, geojson: str):
        layer_name = self.bdot10k_dockwidget.layerComboBox.currentText()
        existing_layer = QgsProject.instance().mapLayersByName(layer_name)

        geojson_layer = QgsVectorLayer(geojson, "temp", "ogr")
        if geojson_layer.featureCount() <= 0 :
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
        self.bdot10k_dockwidget.classComboBox.addItem("")
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
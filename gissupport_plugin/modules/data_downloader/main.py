from os.path import expanduser

from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtWidgets import QToolButton, QMenu, QFileDialog
from qgis.utils import iface
from qgis.core import QgsVectorLayer, QgsCoordinateReferenceSystem, QgsProject, QgsApplication, QgsField, \
    QgsCoordinateTransform, Qgis
from qgis.gui import QgsMessageBarItem

from gissupport_plugin.modules.uldk.uldk.api import ULDKSearchTeryt
from gissupport_plugin.modules.base import BaseModule
from gissupport_plugin.modules.data_downloader.prg.utils import EntityOption, PRGDownloadTask
from gissupport_plugin.modules.data_downloader.bdot10k.utils import BDOT10kDownloadTask
from gissupport_plugin.modules.data_downloader.prg.prg_dockwidget import PRGDockWidget
from gissupport_plugin.modules.data_downloader.bdot10k.bdot10k_dockwidget import BDOT10kDockWidget


class DataDownloaderModule(BaseModule):
    module_name = "Dane do pobrania"

    def __init__(self, parent):
        super().__init__(parent)
        self.pgr_dockwidget = PRGDockWidget()
        self.bdot10k_dockwidget = BDOT10kDockWidget()
        self.bdot10k_filepath = expanduser("~")
        self.teryt_woj = ""
        self.teryt_pow = ""

        self.download_action = self.parent.add_action(
            icon_path=':/plugins/gissupport_plugin/data_downloader/dane_do_pobrania.svg',
            text=self.module_name,
            callback=lambda: None,
            parent=iface.mainWindow(),
            checkable=True,
            add_to_topmenu=True
        )

        self.prg_action = self.parent.add_action(
            icon_path = None,
            text= "PRG - granice administracyjne",
            callback=self.change_pgr_dockwidget_visibility,
            parent=iface.mainWindow(),
            add_to_topmenu=False,
            add_to_toolbar=False,
            checkable=False,
            enabled=True
        )

        self.bdot10k_action = self.parent.add_action(
            icon_path = None,
            text= "BDOT10k - Baza Danych Obiektów Topograficznych",
            callback=self.change_bdot10k_dockwidget_visibility,
            parent=iface.mainWindow(),
            add_to_topmenu=False,
            add_to_toolbar=False,
            checkable=False,
            enabled=True
        )

        self.download_action.setMenu(QMenu())
        main_menu = self.download_action.menu()
        main_menu.addAction(self.prg_action)
        main_menu.addAction(self.bdot10k_action)
        self.toolButton = self.parent.toolbar.widgetForAction(self.download_action)
        self.toolButton.setPopupMode(QToolButton.InstantPopup)

        self.task = None
        self.manager = QgsApplication.taskManager()

        self.populate_dockwidget_comboboxes()
        self.pgr_dockwidget.entity_type_combobox.currentTextChanged.connect(self.handle_entity_type_changed)
        self.pgr_dockwidget.entity_division_combobox.currentTextChanged.connect(self.handle_entity_division_changed)
        self.pgr_dockwidget.btn_download.clicked.connect(self.download_prg)
        self.pgr_dockwidget.filter_line_edit.textChanged.connect(self.filter_name_combobox)

        self.fill_woj_combobox()
        self.bdot10k_dockwidget.browseButton.clicked.connect(self.browse_filepath_for_bdot10k)
        self.bdot10k_dockwidget.wojComboBox.currentTextChanged.connect(self.fill_pow_combobox)
        self.bdot10k_dockwidget.powComboBox.currentTextChanged.connect(self.get_teryt_pow)
        self.bdot10k_dockwidget.downloadButton.clicked.connect(self.download_bdot10k)

    def filter_name_combobox(self, text: str):
        model = self.pgr_dockwidget.entity_name_combobox.model()
        view = self.pgr_dockwidget.entity_name_combobox.view()

        first_hit = 1
        for row in range(model.rowCount()):
            item_text = model.item(row, 0).text()

            if text.lower() not in item_text.lower():
                view.setRowHidden(row, True)
            else:
                if first_hit:
                    self.pgr_dockwidget.entity_name_combobox.setCurrentIndex(row)
                    first_hit = 0
                view.setRowHidden(row, False)

    def download_prg(self):
        entity_division = self.pgr_dockwidget.entity_division_combobox.currentText()
        entity_teryt = self.pgr_dockwidget.entity_name_combobox.currentData()

        crs = QgsCoordinateReferenceSystem()
        crs.createFromSrid(2180)

        self.layer = QgsVectorLayer("MultiPolygon", "Obiekty PRG", "memory")
        self.layer.setCrs(crs)

        dp = self.layer.dataProvider()
        dp.addAttributes([QgsField("Nazwa", QVariant.String)])
        dp.addAttributes([QgsField("TERYT", QVariant.String)])
        self.layer.updateFields()

        self.task = PRGDownloadTask("Pobieranie danych PRG", 75, self.layer,
                                    entity_division, entity_teryt)
        self.manager.addTask(self.task)
        self.task.taskCompleted.connect(self.add_result_layer)

    def populate_dockwidget_comboboxes(self):
        self.pgr_dockwidget.entity_division_combobox.addItem(EntityOption.WOJEWODZTWO.value)
        self.pgr_dockwidget.entity_division_combobox.addItem(EntityOption.POWIAT.value)
        self.pgr_dockwidget.entity_division_combobox.addItem(EntityOption.GMINA.value)

        self.pgr_dockwidget.entity_type_combobox.addItem(EntityOption.BRAK.value)
        self.pgr_dockwidget.entity_type_combobox.addItem(EntityOption.WOJEWODZTWO.value)
        self.pgr_dockwidget.entity_type_combobox.addItem(EntityOption.POWIAT.value)
        self.pgr_dockwidget.entity_type_combobox.addItem(EntityOption.GMINA.value)

    def handle_entity_division_changed(self, entity_division_value: str):
        model = self.pgr_dockwidget.entity_type_combobox.model()
        item = model.item(0, 0)

        if entity_division_value == EntityOption.GMINA.value:
            item.setEnabled(False)
        else:
            item.setEnabled(True)

    def handle_entity_type_changed(self, entity_option_value: str):
        self.pgr_dockwidget.entity_name_combobox.clear()
        self.pgr_dockwidget.filter_line_edit.clear()

        if entity_option_value == EntityOption.WOJEWODZTWO.value:
            data = self.get_administratives("wojewodztwo", enable_filter_line_edit=True)
        elif entity_option_value == EntityOption.POWIAT.value:
            data = self.get_administratives("powiat", enable_filter_line_edit=True)
        elif entity_option_value == EntityOption.GMINA.value:
            data = self.get_administratives("gmina", enable_filter_line_edit=True)
        else:
            self.pgr_dockwidget.filter_line_edit.setEnabled(False)
            return

        for item in data:
            display_name = f'{item[0]} | {item[1]}'
            self.pgr_dockwidget.entity_name_combobox.addItem(display_name, item[1])

    def add_result_layer(self):
        QgsProject.instance().addMapLayer(self.layer)
        self.zoom_to_layer()

    def zoom_to_layer(self):
        proj = QgsProject.instance()

        extent = self.layer.extent()
        if self.layer.crs().authid() != proj.crs().authid():
            transformation = QgsCoordinateTransform(self.layer.crs(), proj.crs(), proj)
            extent = transformation.transform(extent)

        iface.mapCanvas().setExtent(extent)

    def get_administratives(self, level: str, teryt: str = "",
                            enable_filter_line_edit: bool = False):
        """
        Pobiera dane (województwa, powiaty, gminy) dla comboboxów.
        """
        if enable_filter_line_edit:
            self.pgr_dockwidget.filter_line_edit.setEnabled(True)
        search = ULDKSearchTeryt(level, ("nazwa", "teryt"))
        result = search.search(teryt)
        result = [r.split("|") for r in result]

        return result

    def change_pgr_dockwidget_visibility(self):
        """
        Zmienia widoczność widgetu PGR przy wyborze z menu.
        """
        if self.pgr_dockwidget.isVisible():
            iface.removeDockWidget(self.pgr_dockwidget)
        else:
            iface.addDockWidget(Qt.RightDockWidgetArea, self.pgr_dockwidget)

    def change_bdot10k_dockwidget_visibility(self):
        """
        Zmienia widoczność widgetu BDOT10k przy wyborze z menu.
        """
        if self.bdot10k_dockwidget.isVisible():
            iface.removeDockWidget(self.bdot10k_dockwidget)
        else:
            iface.addDockWidget(Qt.RightDockWidgetArea, self.bdot10k_dockwidget)

    def browse_filepath_for_bdot10k(self):
        """
        Uruchamia okno z wyborem miejsca zapisu plików BDOT10k i zapisuje ścieżkę.
        """
        self.bdot10k_filepath = QFileDialog.getExistingDirectory(self.bdot10k_dockwidget,
                                                 'Wybierz miejsce zapisu plików BDOT10k',
                                                 expanduser("~"))
        self.bdot10k_dockwidget.filepathLine.setText(self.bdot10k_filepath)

    def fill_woj_combobox(self):
        """
        Uzupełnia combobox z województwami. Wywoływane raz, przy starcie pluginu.
        """
        wojewodztwa = self.get_administratives("wojewodztwo")
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
        powiaty = self.get_administratives("powiat", self.teryt_woj)
        self.bdot10k_dockwidget.powComboBox.clear()
        self.bdot10k_dockwidget.powComboBox.addItem("")
        for powiat in powiaty:
            display_name = f'{powiat[0]} | {powiat[1]}'
            self.bdot10k_dockwidget.powComboBox.addItem(display_name, powiat[1])

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
        self.task.download_finished.connect(self.show_success_message)
        self.manager.addTask(self.task)

    def update_bdok10k_download_progress(self, value: int):
        """
        Aktualizuje pasek postępu pobierania danych BDOT10k.
        """
        self.bdot10k_dockwidget.progressBar.setValue(value)

    def show_success_message(self):
        """
        Wyświetla komunikat o pomyślnym pobraniu danych BDOT10k.
        """
        iface.messageBar().pushWidget(QgsMessageBarItem("Wtyczka GIS Support",
                    "Pomyślnie pobrano dane BDOT10k", level=Qgis.Info))

from os.path import expanduser

from qgis.core import Qgis, QgsApplication
from qgis.gui import QgsMessageBarItem
from qgis.utils import iface
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QFileDialog

from gissupport_plugin.modules.data_downloader.bdot10k.bdot10k_dockwidget import BDOT10kDockWidget
from gissupport_plugin.modules.data_downloader.bdot10k.utils import BDOT10kDownloadTask
from gissupport_plugin.modules.uldk.uldk.api import ULDKSearchTeryt

class BDOT10kDownloader:

    def __init__(self):
        self.task = None
        self.bdot10k_filepath = expanduser("~")
        self.teryt_woj = ""
        self.teryt_pow = ""

        self.bdot10k_dockwidget = BDOT10kDockWidget()

        self.fill_woj_combobox()
        self.bdot10k_dockwidget.browseButton.clicked.connect(self.browse_filepath_for_bdot10k)
        self.bdot10k_dockwidget.wojComboBox.currentTextChanged.connect(self.fill_pow_combobox)
        self.bdot10k_dockwidget.powComboBox.currentTextChanged.connect(self.get_teryt_pow)
        self.bdot10k_dockwidget.downloadButton.clicked.connect(self.download_bdot10k)


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
        Zmienia widoczność widgetu BDOT10k przy wyborze z menu.
        """
        if self.bdot10k_dockwidget.isVisible():
            iface.removeDockWidget(self.bdot10k_dockwidget)
        else:
            iface.addDockWidget(Qt.RightDockWidgetArea, self.bdot10k_dockwidget)

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

    def get_administratives(self, level: str, teryt: str = ""):
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

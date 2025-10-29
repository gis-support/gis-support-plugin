from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFileDialog
from qgis.gui import QgsMessageBarItem
from qgis.core import QgsApplication, Qgis
from qgis.utils import iface

from gissupport_plugin.modules.data_downloader.prg_address.prg_address_dockwidget import PRGAddressDockWidget
from gissupport_plugin.modules.data_downloader.prg_address.utils import PRGAddressDownloadTask
from gissupport_plugin.tools.teryt import Wojewodztwa, POWIATY


class PRGAddressDownloader:
    def __init__(self):
        self.task = None
        self.prg_address_dockwidget = None

        self.teryt_w = ""
        self.teryt_p = ""

    def init_prg_address_dockwidget(self):
        self.prg_address_dockwidget = PRGAddressDockWidget()
        iface.addDockWidget(Qt.RightDockWidgetArea, self.prg_address_dockwidget)
        self.prg_address_dockwidget.hide()

        self.fill_combobox_w()
        self.fill_combobox_p()

        # pobieranie dla wybranego powiatu
        self.prg_address_dockwidget.browseButton.clicked.connect(self.browse_filepath_for_prg_address)
        self.prg_address_dockwidget.wComboBox.currentTextChanged.connect(self.fill_combobox_p)
        self.prg_address_dockwidget.pComboBox.currentTextChanged.connect(self.get_teryt_pow)
        self.prg_address_dockwidget.pDownloadBtn.clicked.connect(self.download_prg_address)


    def change_prg_address_dockwidget_visibility(self):
        """
        Zmienia widoczność widgetu prg przy wyborze z menu. Inicjuje widget przy pierwszym uruchomieniu.
        """
        if self.prg_address_dockwidget is None:
            self.init_prg_address_dockwidget()
        self.prg_address_dockwidget.setVisible(not self.prg_address_dockwidget.isVisible())


    ### pobieranie dla wybranego powiatu
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
        Uruchamia okno z wyborem miejsca zapisu plików BDOT10k i zapisuje ścieżkę.
        """
        prg_address_filepath = QFileDialog.getExistingDirectory(self.prg_address_dockwidget,
                                                 'Wybierz miejsce zapisu punktów adresowych PRG')
        self.prg_address_dockwidget.filePathLineEdit.setText(prg_address_filepath)

    def download_prg_address(self):
        """
        Uruchamia pobieranie danych BDOT10k.
        """
        if self.teryt_w == "" or self.teryt_p == "":
            iface.messageBar().pushMessage("Przed pobraniem należy wybrać województwo i powiat",
                                           level=Qgis.Warning)
            return

        prg_address_filepath = self.prg_address_dockwidget.filePathLineEdit.text()
        if not prg_address_filepath or prg_address_filepath == "":
            iface.messageBar().pushMessage("Przed pobraniem należy wybrać ścieżkę zapisu danych",
                                           level=Qgis.Warning)
            return

        self.task = PRGAddressDownloadTask("Pobieranie punktów adresowych PRG",
                                        teryt_p=self.teryt_p, filepath=prg_address_filepath)
        self.task.progress_updated.connect(self.update_prg_address_download_progress)
        self.task.download_finished.connect(self.show_prg_address_success_message)
        self.task.task_failed.connect(self.handle_prg_address_task_error)

        manager = QgsApplication.taskManager()
        manager.addTask(self.task)

        # self.select_features_tool.deactivate()
        # self.select_features_freehand_tool.deactivate()
        # self.select_features_rectangle_tool.deactivate()

    def update_prg_address_download_progress(self, value: int):
        """
        Aktualizuje pasek postępu pobierania danych BDOT10k.
        """
        self.task.setProgress(value)

    def show_prg_address_success_message(self):
        """
        Wyświetla komunikat o pomyślnym pobraniu danych BDOT10k.
        """
        iface.messageBar().pushWidget(QgsMessageBarItem("Wtyczka GIS Support",
                    "Pomyślnie pobrano dane BDOT10k", level=Qgis.Info))

    def handle_prg_address_task_error(self, error_message):
        iface.messageBar().pushMessage("Wtyczka GIS Support", error_message, level=Qgis.Critical)

    ### POBIEARNIE DLA ZASIĘGU



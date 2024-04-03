from qgis.PyQt.QtWidgets import QToolButton, QMenu
from qgis.utils import iface


from gissupport_plugin.modules.base import BaseModule
from gissupport_plugin.modules.data_downloader.bdot10k.downloader import BDOT10kDownloader
from gissupport_plugin.modules.data_downloader.prg.downloader import PRGDownloader

class DataDownloaderModule(BaseModule, PRGDownloader, BDOT10kDownloader):
    module_name = "Dane do pobrania"

    def __init__(self, parent):
        super().__init__(parent)
        PRGDownloader.__init__(self)
        BDOT10kDownloader.__init__(self)

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
            callback=self.change_prg_dockwidget_visibility,
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

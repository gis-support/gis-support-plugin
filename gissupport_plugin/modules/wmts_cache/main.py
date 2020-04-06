from gissupport_plugin.modules.base import BaseModule
from gissupport_plugin.modules.wmts_cache.wmts_cache_dialog import WMTSCacheDialog
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QMenu, QAction, QWidget, QToolButton
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import QPoint
from qgis.core import Qgis
from owslib.wmts import WebMapTileService
from requests.exceptions import ConnectionError, ReadTimeout
from os import path
import json

class WMTSCacheModule(BaseModule):
    module_name = "Narzędzie do szybkiego wczytywania WMTS"

    def __init__(self, parent):
        super().__init__(parent)

        self.action = self.parent.add_action(
            '',
            self.module_name,
            self.showMenu,
            parent=iface.mainWindow(),
            checkable=True,
            add_to_topmenu=False
        )
        self.dialog = WMTSCacheDialog()
        self.dialog.lbInfoCacheExpiration.setPixmap(QPixmap(':/plugins/plugin/info.png'))
        self.dialog.lbInfoCacheExpiration.setToolTip('Maksymalnie 720 godz. (30 dni)')

        self.actionMenu = None
        self.wmtsCapabilitiesData = []
        self.cacheSettings = QAction('Ustawienia')
        self.cacheExpirationValue = 0

        self.toolButton = self.parent.toolbar.widgetForAction(self.action)
        self.toolButton.setPopupMode(QToolButton.InstantPopup)
        self.cacheSettings.triggered.connect(self.showCacheSettings)
        self.dialog.accepted.connect(self.dialogAccepted)

        self.initMenu()

    def initMenu(self):
        self.action.setMenu(QMenu())
        self.actionMenu = self.action.menu()
        with open(path.join(path.dirname(__file__), 'services.json')) as file:
            services = json.load(file)
            for service in services:
                try:
                    # wmts = WebMapTileService(service['url']+'?service=WMTS&request=getCapabilities', version='1.0.0')
                    menu = self.actionMenu.addMenu(service['name'])
                    # for layer in wmts.contents:
                    #     name = wmts[layer].name
                    #     menu.addAction(name)           
                except (ConnectionError, ReadTimeout):
                    pass

            self.actionMenu.addSeparator()
            self.actionMenu.addAction(self.cacheSettings)

    def showMenu(self):
        pass

    def dialogAccepted(self):
        self.cacheExpirationValue = self.dialog.sbCacheExpiration.value()

    def showCacheSettings(self):
        self.dialog.show()        

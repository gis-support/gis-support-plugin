from gissupport_plugin.modules.base import BaseModule
from gissupport_plugin.modules.wmts_cache.wmts_cache_dialog import WMTSCacheDialog
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QMenu, QAction, QWidget, QToolButton
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import QPoint
from qgis.core import Qgis, QgsRasterLayer, QgsProject
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
            callback = lambda: None,
            parent=iface.mainWindow(),
            checkable=True,
            add_to_topmenu=False
        )
        self.dialog = WMTSCacheDialog()
        self.dialog.lbInfoCacheExpiration.setPixmap(QPixmap(':/plugins/plugin/info.png'))
        self.dialog.lbInfoCacheExpiration.setToolTip('Maksymalnie 720 godz. (30 dni)')

        self.actionMenu = None
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
                    wmts = WebMapTileService(service['url']+'?service=WMTS&request=getCapabilities')
                    menu = self.actionMenu.addMenu(service['name'])

                    for layer in wmts.contents:
                        wmts_layer = wmts[layer]

                        if service['format'] not in wmts_layer.formats:
                            service['format'] = wmts_layer.formats[0]
                        
                        if service['crs'] not in wmts_layer.tilematrixsetlinks.keys():
                            service['crs'] = list(wmts_layer.tilematrixsetlinks.keys())[0]

                        name = wmts_layer.name
                        action = menu.addAction(name)
                        service.update({'layer_name': name})

                        action.setData(service)
                        action.triggered.connect(lambda checked, action=action: self.addToProject(checked, action))

                except (ConnectionError, ReadTimeout):
                    pass

            self.actionMenu.addSeparator()
            self.actionMenu.addAction(self.cacheSettings)

    def addToProject(self, checked, menu_action):
        params = menu_action.data()
        wmts_url = (
            "contextualWMSLegend=0&crs={}&dpiMode=0&"
            "featureCount=10&format={}&layers={}&"
            "styles=default&tileMatrixSet={}&url={}".format(
                params['crs'],
                params['format'],
                params['layer_name'],
                params['crs'],
                params['url']+'?service%3DWMTS%26request%3DgetCapabilities'
            )
        )
        layer = QgsRasterLayer(wmts_url, params['name'], 'wms')
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
        else:
            iface.messageBar().pushMessage(
                'WMTS Cache',
                f'Nie udało się wczytać warstwy {params["name"]}',
                level=Qgis.Warning
            )

    def dialogAccepted(self):
        self.cacheExpirationValue = self.dialog.sbCacheExpiration.value()

    def showCacheSettings(self):
        self.dialog.show()        

from gissupport_plugin.modules.base import BaseModule
from gissupport_plugin.modules.wmts.wmts_cache_dialog import WMTSCacheDialog
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QMenu, QAction, QWidget, QToolButton
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import QPoint, QSettings
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
            ':/plugins/gissupport_plugin/wmts/wmts.svg',
            self.module_name,
            callback = lambda: None,
            parent=iface.mainWindow(),
            checkable=True,
            add_to_topmenu=True
        )
        self.settings = QSettings()

        self.dialog = WMTSCacheDialog()
        self.dialog.lbInfoCacheExpiration.setPixmap(QPixmap(':/plugins/plugin/info.png'))
        self.dialog.lbInfoCacheExpiration.setToolTip('Maksymalnie 720 godz. (30 dni)')
        self.cacheSettings = QAction('Ustawienia')

        self.toolButton = self.parent.toolbar.widgetForAction(self.action)
        self.toolButton.setPopupMode(QToolButton.InstantPopup)
        self.cacheSettings.triggered.connect(self.showCacheSettings)
        self.dialog.accepted.connect(self.dialogAccepted)

        self.actionMenu = None
        self.initMenu()

    def initMenu(self):
        self.action.setMenu(QMenu())
        self.actionMenu = self.action.menu()

        with open(path.join(path.dirname(__file__), 'services.json'), encoding='utf-8') as file:
            services = json.load(file)

            for service in services:
                action = self.actionMenu.addAction(service['name'])
                action.setData(service)
                action.triggered.connect(lambda checked, action=action: self.addToProject(checked, action))

            self.actionMenu.addSeparator()
            self.actionMenu.addAction(self.cacheSettings)

    def addToProject(self, checked, menu_action):
        params = menu_action.data()
        project_crs = iface.mapCanvas().mapSettings().destinationCrs().authid()
        crs = project_crs if project_crs in params['supported_crs'] else 'EPSG:2180'
        
        wmts_url = (
            "contextualWMSLegend=0&crs={}&dpiMode=0&"
            "featureCount=10&format={}&layers={}&"
            "styles=default&tileMatrixSet={}&url={}".format(
                crs,
                params['format'],
                params['tiles_name'],
                crs,
                params['url']+'?service%3DWMTS%26request%3DgetCapabilities'
            )
        )
        
        layer = QgsRasterLayer(wmts_url, params['name'], 'wms')
        if layer.isValid():
            root = QgsProject.instance().layerTreeRoot()
            QgsProject.instance().addMapLayer(layer, False)
            root.insertLayer(len(root.children()), layer)
        else:
            iface.messageBar().pushMessage(
                'WMTS Cache',
                f'Nie udało się wczytać warstwy {params["name"]}',
                level=Qgis.Warning
            )
        
    def dialogAccepted(self):
        self.settings.setValue('/qgis/defaultTileExpiry', self.dialog.sbCacheExpiration.value())

    def showCacheSettings(self):
        tile_expiry = int(self.settings.value('/qgis/defaultTileExpiry', 24))
        self.dialog.sbCacheExpiration.setValue(tile_expiry)
        self.dialog.show()        

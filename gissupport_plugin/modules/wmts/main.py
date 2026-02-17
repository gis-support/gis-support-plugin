from gissupport_plugin.modules.base import BaseModule
from qgis.utils import iface
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import QSettings
from qgis.core import Qgis, QgsRasterLayer, QgsProject
from os import path
import json

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem

from gissupport_plugin.modules.wmts.wmts_dockwidget import WMTSDockWidget

class WMTSCacheModule(BaseModule):
    module_name = "Narzędzie do szybkiego wczytywania WMTS"

    def __init__(self, parent):
        super().__init__(parent)
        self.dockwidget = WMTSDockWidget()
        self.list_model = QStandardItemModel()

        self.action = self.parent.add_dockwidget_action(
            dockwidget=self.dockwidget,
            icon_path=':/plugins/gissupport_plugin/wmts/wmts.svg',
            text=self.module_name,
            add_to_topmenu=True
        )
        self.settings = QSettings()

        self.dockwidget.lbInfoCacheExpiration.setPixmap(QPixmap(':/plugins/plugin/info.png'))
        self.dockwidget.lbInfoCacheExpiration.setToolTip('Maksymalnie 720 godz. (30 dni)')
        self.dockwidget.saveButton.clicked.connect(self.dialogAccepted)

        self.initMenu()

    def initMenu(self):

        with open(path.join(path.dirname(__file__), 'services.json'), encoding='utf-8') as file:
            services = json.load(file)

            for service in services:
                service_item = QStandardItem(service['name'])
                service_item.setData(service)
                self.list_model.appendRow(service_item)
            
        self.dockwidget.listView.setModel(self.list_model)
        self.dockwidget.listView.doubleClicked.connect(self.addToProject)
        self.dockwidget.listView.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        tile_expiry = int(self.settings.value('/qgis/defaultTileExpiry', 24))
        self.dockwidget.sbCacheExpiration.setValue(tile_expiry)


    def addToProject(self, index):
        service_data = self.list_model.itemFromIndex(index).data()
        project_crs = iface.mapCanvas().mapSettings().destinationCrs().authid()
        crs = project_crs if project_crs in service_data['supported_crs'] else 'EPSG:2180'
        
        wmts_url = (
            "contextualWMSLegend=0&crs={}&dpiMode=0&"
            "featureCount=10&format={}&layers={}&"
            "styles=default&tileMatrixSet={}&url={}".format(
                crs,
                service_data['format'],
                service_data['tiles_name'],
                crs,
                service_data['url']+'?service%3DWMTS%26request%3DgetCapabilities'
            )
        )
        
        layer = QgsRasterLayer(wmts_url, service_data['name'], 'wms')
        if layer.isValid():
            root = QgsProject.instance().layerTreeRoot()
            QgsProject.instance().addMapLayer(layer, False)
            root.insertLayer(len(root.children()), layer)
        else:
            iface.messageBar().pushMessage(
                'WMTS Cache',
                f'Nie udało się wczytać warstwy {service_data["name"]}',
                level=Qgis.MessageLevel.Warning
            )
        
    def dialogAccepted(self):
        self.settings.setValue('/qgis/defaultTileExpiry', self.dockwidget.sbCacheExpiration.value())

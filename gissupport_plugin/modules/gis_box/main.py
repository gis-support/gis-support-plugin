from qgis.PyQt.QtGui import QIcon
from qgis.utils import iface
from qgis.core import QgsProject
from PyQt5 import QtWidgets

from gissupport_plugin.modules.base import BaseModule
from gissupport_plugin.modules.gis_box.modules.auto_digitization.gui.widget import AutoDigitizationWidget
from gissupport_plugin.tools.gisbox_connection import GISBOX_CONNECTION
from gissupport_plugin.modules.gis_box.layers.layers_registry import layers_registry
from gissupport_plugin.tools.logger import Logger
from gissupport_plugin.modules.gis_box.gisbox_dockwidget import GISBoxDockWidget

class GISBox(BaseModule, Logger):

    def __init__(self, parent):
        super().__init__(parent)
        self.parent.toolbar.addSeparator()
        self.dockwidget = GISBoxDockWidget()
        self.autoDigitizationWidget = None

        self.dockwidgetAction = self.parent.add_action(
            icon_path=":/plugins/gissupport_plugin/gis_box/disconnected.png",
            text = 'GIS.Box',
            callback=self.dockwidget.toggle_widget_visibility,
            parent=iface.mainWindow(),
            add_to_menu=False,
            add_to_topmenu=False,
            add_to_toolbar=True,
            checkable=True,
            enabled=True
        )

        self.dockwidget.visibilityChanged.connect(self.dockwidgetAction.setChecked)
        layers_registry.on_schema.connect(self.readProject)
        QgsProject.instance().readProject.connect(self.readProject)
        QgsProject.instance().readProject.connect(self.toggle_gisbox_layers_readonly_mode)
        self.dockwidget.connectButton.clicked.connect(self.onConnection)
        self.mount_autodigitization_widget()

    def onConnection(self, connect: bool):
        """ Połączenie/rozłączenie z serwerem """

        connected = connect and GISBOX_CONNECTION.connect()
        self.dockwidget.authSettingsButton.setEnabled(not connected)
        if connected:
            # Połączono z serwerem
            self.dockwidgetAction.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/connected.png"))
            self.dockwidget.connectButton.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/widget_disconnect.svg"))
            self.dockwidget.connectButton.setText('Wyloguj')
            self.dockwidget.refreshButton.setEnabled(True)

            GISBOX_CONNECTION.get(
                "/api/settings/automatic_digitization_module_enabled?value_only=true", callback=self.enableDigitization
            )

        else:
            # Rozłączono z serwerem lub błąd połączenia

            GISBOX_CONNECTION.disconnect()

            self.dockwidgetAction.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/disconnected.png"))
            self.dockwidget.connectButton.setIcon(QIcon(":/plugins/gissupport_plugin/gis_box/widget_connect.svg"))
            self.dockwidget.connectButton.setText('Zaloguj')
            self.dockwidget.refreshButton.setEnabled(False)
            self.dockwidget.connectButton.setChecked(False)
            self.dockwidget.clear_treeview()
            self.dockwidget.vectorTab.setEnabled(False)
        
        self.toggle_gisbox_layers_readonly_mode()


    def toggle_gisbox_layers_readonly_mode(self):
        """
        Przełącza tryb `read_only` warstw GIS.Box.
        Wykorzystywane przy łączeniu/rozłączaniu z GIS.Box.
        """
        is_connected = GISBOX_CONNECTION.is_connected
        for layer in QgsProject.instance().mapLayers().values():
            if layers_registry.isGisboxLayer(layer):

                if is_connected:
                    # Odczytywanie uprawnień użytkownika do edycji warstwy
                    layer_id = layer.customProperty('gisbox/layer_id')
                    layer_permission = GISBOX_CONNECTION.current_user['permissions']['layers'].get(int(layer_id))

                    if layer_permission['main_value'] == 2:
                        layer.setReadOnly(False)
                    
                    else:
                        layer.setReadOnly(True)

                else:
                    if layer.isEditable():
                        layer.rollBack()
                    layer.setReadOnly(True)

    def readProject(self):
        if not GISBOX_CONNECTION.is_connected:
            return
        for layer in QgsProject.instance().mapLayers().values():
            if layers_registry.isGisboxLayer(layer):
                layer_class = layers_registry.layers[int(
                    layer.customProperty('gisbox/layer_id'))]
                layer_class.setLayer(layer, from_project=True)
                

    def mount_autodigitization_widget(self):
        self.autoDigitizationWidget = AutoDigitizationWidget()
        layout = QtWidgets.QVBoxLayout()
        self.dockwidget.vectorTab.setLayout(layout)
        layout.addWidget(self.autoDigitizationWidget)
        self.dockwidget.vectorTab.setEnabled(False)

    def enableDigitization(self, data):
        if data["data"]:
            self.checkDigitizationPermissions()

    def checkDigitizationPermissions(self):
        module = GISBOX_CONNECTION.current_user["permissions"]["modules"].get("AUTOMATIC_DIGITIZATION")
        if module["main_value"] == 1:
            self.dockwidget.vectorTab.setEnabled(True)
            self.autoDigitizationWidget.getOptions()
            return

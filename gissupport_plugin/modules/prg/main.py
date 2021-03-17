from typing import List

from qgis.PyQt.QtCore import Qt, QVariant
from qgis.utils import iface
from qgis.core import QgsVectorLayer, QgsFeature, QgsCoordinateReferenceSystem, QgsProject, QgsApplication, QgsField, \
    QgsCoordinateTransform, Qgis

from gissupport_plugin.modules.uldk.uldk.api import ULDKSearchTeryt, ULDKSearchLogger
from gissupport_plugin.modules.base import BaseModule
from gissupport_plugin.modules.prg.utils import EntityOption, PRGDownloadTask
from gissupport_plugin.modules.prg.prg_dockwidget import PRGDockWidget


class PRGModule(BaseModule):
    module_name = "PRG - granice administracyjne"

    def __init__(self, parent):
        super().__init__(parent)

        self.dockwidget = PRGDockWidget()
        iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
        self.dockwidget.hide()

        self.action = self.parent.add_action(
            ':/plugins/gissupport_plugin/prg/prg.svg',
            self.module_name,
            callback=lambda state: self.dockwidget.setHidden(not state),
            parent=iface.mainWindow(),
            checkable=True,
            add_to_topmenu=True
        )

        self.populate_dockwidget_comboboxes()
        self.task = None
        self.manager = QgsApplication.taskManager()

        self.dockwidget.entity_type_combobox.currentTextChanged.connect(self.handle_entity_type_changed)
        self.dockwidget.entity_division_combobox.currentTextChanged.connect(self.handle_entity_division_changed)
        self.dockwidget.btn_download.clicked.connect(self.download_prg)
        self.dockwidget.filter_line_edit.textChanged.connect(self.filter_name_combobox)

    def filter_name_combobox(self, text: str):
        model = self.dockwidget.entity_name_combobox.model()
        view = self.dockwidget.entity_name_combobox.view()

        first_hit = 1
        for row in range(model.rowCount()):
            item_text = model.item(row, 0).text()

            if text.lower() not in item_text.lower():
                view.setRowHidden(row, True)
            else:
                if first_hit:
                    self.dockwidget.entity_name_combobox.setCurrentIndex(row)
                    first_hit = 0
                view.setRowHidden(row, False)

    def download_prg(self):
        entity_division = self.dockwidget.entity_division_combobox.currentText()
        entity_teryt = self.dockwidget.entity_name_combobox.currentData()

        crs = QgsCoordinateReferenceSystem()
        crs.createFromSrid(2180)

        self.layer = QgsVectorLayer("MultiPolygon", "Obiekty PRG", "memory")
        self.layer.setCrs(crs)

        dp = self.layer.dataProvider()
        dp.addAttributes([QgsField("Nazwa", QVariant.String)])
        dp.addAttributes([QgsField("TERYT", QVariant.String)])
        self.layer.updateFields()

        self.task = PRGDownloadTask("Pobieranie danych PRG", 75, self.layer, entity_division, entity_teryt)
        self.manager.addTask(self.task)
        self.task.taskCompleted.connect(self.add_result_layer)

    def populate_dockwidget_comboboxes(self):
        self.dockwidget.entity_division_combobox.addItem(EntityOption.WOJEWODZTWO.value)
        self.dockwidget.entity_division_combobox.addItem(EntityOption.POWIAT.value)
        self.dockwidget.entity_division_combobox.addItem(EntityOption.GMINA.value)

        self.dockwidget.entity_type_combobox.addItem(EntityOption.BRAK.value)
        self.dockwidget.entity_type_combobox.addItem(EntityOption.WOJEWODZTWO.value)
        self.dockwidget.entity_type_combobox.addItem(EntityOption.POWIAT.value)
        self.dockwidget.entity_type_combobox.addItem(EntityOption.GMINA.value)

    def handle_entity_division_changed(self, entity_division_value: str):
        model = self.dockwidget.entity_type_combobox.model()
        item = model.item(0, 0)

        if entity_division_value == EntityOption.GMINA.value:
            item.setEnabled(False)
        else:
            item.setEnabled(True)

    def handle_entity_type_changed(self, entity_option_value: str):
        self.dockwidget.entity_name_combobox.clear()
        self.dockwidget.filter_line_edit.clear()

        if entity_option_value == EntityOption.WOJEWODZTWO.value:
            data = self.get_administratives("wojewodztwo")
        elif entity_option_value == EntityOption.POWIAT.value:
            data = self.get_administratives("powiat")
        elif entity_option_value == EntityOption.GMINA.value:
            data = self.get_administratives("gmina")
        else:
            self.dockwidget.filter_line_edit.setEnabled(False)
            return

        for item in data:
            display_name = f'{item[0]} | {item[1]}'
            self.dockwidget.entity_name_combobox.addItem(display_name, item[1])

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

    def get_administratives(self, level: str):
        self.dockwidget.filter_line_edit.setEnabled(True)

        search = ULDKSearchTeryt(level, ("nazwa", "teryt"))
        result = search.search("")
        result = [r.split("|") for r in result]

        return result

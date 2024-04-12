from qgis.PyQt.QtCore import Qt, QVariant
from qgis.core import QgsVectorLayer, QgsCoordinateReferenceSystem, QgsProject, QgsApplication, QgsField, \
    QgsCoordinateTransform
from qgis.utils import iface

from gissupport_plugin.modules.data_downloader.prg.utils import EntityOption, PRGDownloadTask
from gissupport_plugin.modules.data_downloader.prg.prg_dockwidget import PRGDockWidget
from gissupport_plugin.modules.uldk.uldk.api import ULDKSearchTeryt


class PRGDownloader:

    def __init__(self):
        self.prg_dockwidget = PRGDockWidget()
        self.layer = None
        self.task = None

        self.populate_dockwidget_comboboxes()
        self.prg_dockwidget.entity_type_combobox.currentTextChanged.connect(self.handle_entity_type_changed)
        self.prg_dockwidget.entity_division_combobox.currentTextChanged.connect(self.handle_entity_division_changed)
        self.prg_dockwidget.btn_download.clicked.connect(self.download_prg)
        self.prg_dockwidget.filter_line_edit.textChanged.connect(self.filter_name_combobox)


    def change_prg_dockwidget_visibility(self):
        """
        Zmienia widoczność widgetu prg przy wyborze z menu.
        """
        if self.prg_dockwidget.isVisible():
            iface.removeDockWidget(self.prg_dockwidget)
        else:
            iface.addDockWidget(Qt.RightDockWidgetArea, self.prg_dockwidget)


    def filter_name_combobox(self, text: str):
        model = self.prg_dockwidget.entity_name_combobox.model()
        view = self.prg_dockwidget.entity_name_combobox.view()

        first_hit = 1
        for row in range(model.rowCount()):
            item_text = model.item(row, 0).text()

            if text.lower() not in item_text.lower():
                view.setRowHidden(row, True)
            else:
                if first_hit:
                    self.prg_dockwidget.entity_name_combobox.setCurrentIndex(row)
                    first_hit = 0
                view.setRowHidden(row, False)

    def download_prg(self):
        entity_division = self.prg_dockwidget.entity_division_combobox.currentText()
        entity_teryt = self.prg_dockwidget.entity_name_combobox.currentData()

        crs = QgsCoordinateReferenceSystem.fromEpsgId(2180)

        self.layer = QgsVectorLayer("MultiPolygon", "Obiekty PRG", "memory")
        self.layer.setCrs(crs)

        dp = self.layer.dataProvider()
        dp.addAttributes([QgsField("Nazwa", QVariant.String)])
        dp.addAttributes([QgsField("TERYT", QVariant.String)])
        self.layer.updateFields()

        self.task = PRGDownloadTask("Pobieranie danych PRG", 75, self.layer,
                                    entity_division, entity_teryt)
        
        manager = QgsApplication.taskManager()
        manager.addTask(self.task)
        self.task.taskCompleted.connect(self.add_result_layer)

    def populate_dockwidget_comboboxes(self):
        self.prg_dockwidget.entity_division_combobox.addItem(EntityOption.WOJEWODZTWO.value)
        self.prg_dockwidget.entity_division_combobox.addItem(EntityOption.POWIAT.value)
        self.prg_dockwidget.entity_division_combobox.addItem(EntityOption.GMINA.value)

        self.prg_dockwidget.entity_type_combobox.addItem(EntityOption.BRAK.value)
        self.prg_dockwidget.entity_type_combobox.addItem(EntityOption.WOJEWODZTWO.value)
        self.prg_dockwidget.entity_type_combobox.addItem(EntityOption.POWIAT.value)
        self.prg_dockwidget.entity_type_combobox.addItem(EntityOption.GMINA.value)

    def handle_entity_division_changed(self, entity_division_value: str):
        model = self.prg_dockwidget.entity_type_combobox.model()
        item = model.item(0, 0)

        if entity_division_value == EntityOption.GMINA.value:
            item.setEnabled(False)
        else:
            item.setEnabled(True)

    def handle_entity_type_changed(self, entity_option_value: str):
        self.prg_dockwidget.entity_name_combobox.clear()
        self.prg_dockwidget.filter_line_edit.clear()

        if entity_option_value == EntityOption.WOJEWODZTWO.value:
            data = self.get_administratives("wojewodztwo")
        elif entity_option_value == EntityOption.POWIAT.value:
            data = self.get_administratives("powiat")
        elif entity_option_value == EntityOption.GMINA.value:
            data = self.get_administratives("gmina")
        else:
            self.prg_dockwidget.filter_line_edit.setEnabled(False)
            return

        for item in data:
            display_name = f'{item[0]} | {item[1]}'
            self.prg_dockwidget.entity_name_combobox.addItem(display_name, item[1])

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

    def get_administratives(self, level: str, teryt: str = ""):
        """
        Pobiera dane (województwa, powiaty, gminy) dla comboboxów.
        """
        self.prg_dockwidget.filter_line_edit.setEnabled(True)
        search = ULDKSearchTeryt(level, ("nazwa", "teryt"))
        result = search.search(teryt)
        result = [r.split("|") for r in result]

        return result

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsField,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.utils import iface

from gissupport_plugin.modules.data_downloader.prg.prg_dockwidget import PRGDockWidget
from gissupport_plugin.modules.data_downloader.prg.utils import (
    EntityOption,
    PRGDownloadTask,
)
from gissupport_plugin.modules.uldk.uldk.api import ULDKSearchTeryt


class PRGDownloader:

    def __init__(self):
        self.prg_dockwidget = None
        self.layer = None
        self.task = None
        self.entity_option = EntityOption.WOJEWODZTWO

    def init_prg_dockwidget(self):
        self.prg_dockwidget = PRGDockWidget()
        self.populate_dockwidget_comboboxes()
        # self.prg_dockwidget.entity_type_combobox.currentTextChanged.connect(self.handle_entity_type_changed)
        self.prg_dockwidget.entity_division_combobox.currentTextChanged.connect(self.handle_entity_division_changed)
        self.prg_dockwidget.btn_download.clicked.connect(self.download_prg)
        self.prg_dockwidget.filter_line_edit.textChanged.connect(self.filter_name_combobox)

        self.prg_dockwidget.entity_name_combobox.setVisible(False)
        self.prg_dockwidget.name_label.setVisible(False)

        iface.addDockWidget(Qt.RightDockWidgetArea, self.prg_dockwidget)
        self.prg_dockwidget.hide()

    def change_prg_dockwidget_visibility(self):
        """
        Zmienia widoczność widgetu prg przy wyborze z menu. Inicjuje widget przy pierwszym uruchomieniu.
        """
        if self.prg_dockwidget is None:
            self.init_prg_dockwidget()
        self.prg_dockwidget.setVisible(not self.prg_dockwidget.isVisible())

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
        entity_teryt = self.prg_dockwidget.entity_name_combobox.currentData()

        crs = QgsCoordinateReferenceSystem.fromEpsgId(2180)

        self.layer = QgsVectorLayer("MultiPolygon", "Obiekty PRG", "memory")
        self.layer.setCrs(crs)

        dp = self.layer.dataProvider()
        dp.addAttributes([QgsField("Nazwa", QVariant.String)])
        dp.addAttributes([QgsField("TERYT", QVariant.String)])
        self.layer.updateFields()

        self.task = PRGDownloadTask("Pobieranie danych PRG", 75, self.layer,
                                    self.entity_option, entity_teryt)

        manager = QgsApplication.taskManager()
        manager.addTask(self.task)
        self.task.taskCompleted.connect(self.add_result_layer)

    def populate_dockwidget_comboboxes(self):

        value_list = [
            "województw dla całego kraju",
            "wybranego województwa",
            "powiatów dla całego kraju",
            "powiatów dla wybranego województwa",
            "wybranego powiatu",
            # "gmin dla całego kraju",
            "gmin dla wybranego województwa",
            "gmin dla wybranego powiatu",
            "wybranej gminy"
        ]

        self.prg_dockwidget.entity_division_combobox.addItems(value_list)

    def handle_entity_division_changed(self, entity_division_value: str):
        first_word = entity_division_value.split(" ")[0]
        last_word = entity_division_value.split(" ")[-1]

        self.prg_dockwidget.entity_name_combobox.clear()

        if last_word == "kraju":
            self.prg_dockwidget.entity_name_combobox.setVisible(False)
            self.prg_dockwidget.name_label.setVisible(False)
            self.entity_option = EntityOption(first_word[:3])
        
        else:
            self.prg_dockwidget.entity_name_combobox.setVisible(True)
            self.prg_dockwidget.name_label.setVisible(True)

            if first_word in ["wybranego", "wybranej"]:
                self.prg_dockwidget.filter_line_edit.setEnabled(False)
                self.entity_option = EntityOption(last_word[:3])

            else:
                self.entity_option = EntityOption(first_word[:3])

            if last_word == "województwa":
                data = self.get_administratives("wojewodztwo")
            elif last_word == "powiatu":
                data = self.get_administratives("powiat")
            elif last_word == "gminy":
                data = self.get_administratives("gmina")

            for item in data:
                display_name = f'{item[0]} | {item[1]}'
                self.prg_dockwidget.entity_name_combobox.addItem(display_name, item[1])

            self.prg_dockwidget.filter_line_edit.setEnabled(True)

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

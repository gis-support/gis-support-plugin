from os.path import expanduser

from qgis.core import (Qgis, QgsApplication, QgsGeometry, QgsMapLayerProxyModel,
                       QgsCoordinateReferenceSystem, QgsProject, QgsCoordinateTransform, QgsRasterLayer,
                       QgsDistanceArea, QgsUnitTypes, QgsCoordinateTransformContext, QgsRectangle)
from qgis.gui import QgsMessageBarItem
from qgis.utils import iface
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QFileDialog

from gissupport_plugin.modules.data_downloader.nmpt.nmpt_dockwidget import NMPTdockWidget
from gissupport_plugin.modules.gis_box.modules.auto_digitization.tools import SelectRectangleTool
from gissupport_plugin.modules.data_downloader.nmpt.utils import NMPTdownloadTask

def update_download_button_state_dec(func):

    def wrapper(self, *args, **kwargs):

        result = func(self, *args, **kwargs)
        self.update_download_button_state()

        return result

    return wrapper


class NMPTdownloader:

    def __init__(self):

        self.nmpt_dockwidget = None
        self.source_layer = None
        self.selectRectangleTool = None
        self.bbox = None
        self.area_under_limit = True
        self.data_format = None
        self.datum_format = None
        self.nmpt_filepath = expanduser("~")
        self.task = None

        self.init_nmpt_dockwidget()

    def update_download_button_state(self):

        if self.data_format and self.datum_format and self.bbox and self.area_under_limit:
            self.nmpt_dockwidget.downloadButton.setEnabled(True)

        else:
            self.nmpt_dockwidget.downloadButton.setEnabled(False)

    def init_nmpt_dockwidget(self):

        self.nmpt_dockwidget = NMPTdockWidget()
        # self.nmpt_dockwidget.projectLayerList.setFilters(QgsMapLayerProxyModel.PointLayer |
        #                                                  QgsMapLayerProxyModel.LineLayer |
        #                                                  QgsMapLayerProxyModel.PolygonLayer)

        # self.nmpt_dockwidget.selectedOnlyCheckBox.setEnabled(False)
        # self.nmpt_dockwidget.selectedOnlyCheckBox.stateChanged.connect(
        #                                     self.get_bbox_and_area_for_selected)

        self.nmpt_dockwidget.browseButton.clicked.connect(self.browse_filepath_for_nmpt)

        self.nmpt_dockwidget.nmtAsciiRadioButton.toggled.connect(lambda:self.data_radiobutton_state(
            self.nmpt_dockwidget.nmtAsciiRadioButton))
        self.nmpt_dockwidget.nmtGeotiffRadioButton.toggled.connect(
                                    lambda: self.data_radiobutton_state(
                                    self.nmpt_dockwidget.nmtGeotiffRadioButton))
        self.nmpt_dockwidget.nmptRadioButton.toggled.connect(lambda: self.data_radiobutton_state(
            self.nmpt_dockwidget.nmptRadioButton))
        self.nmpt_dockwidget.kronRadioButton.toggled.connect(lambda: self.data_radiobutton_state(
            self.nmpt_dockwidget.kronRadioButton))
        self.nmpt_dockwidget.evrfRadioButton.toggled.connect(lambda: self.data_radiobutton_state(
            self.nmpt_dockwidget.evrfRadioButton))

        self.select_features_rectangle_tool = self.nmpt_dockwidget.selectAreaWidget.select_features_rectangle_tool
        self.select_features_freehand_tool = self.nmpt_dockwidget.selectAreaWidget.select_features_freehand_tool
        self.select_features_tool = self.nmpt_dockwidget.selectAreaWidget.select_features_tool

        # self.selectRectangleTool = SelectRectangleTool(self.nmpt_dockwidget)
        # self.selectRectangleTool.setButton(self.nmpt_dockwidget.selectAreaButton)
        # self.nmpt_dockwidget.selectAreaButton.clicked.connect(lambda: self.activateTool(
        #                                                         self.selectRectangleTool))
        self.select_features_rectangle_tool.geometryChanged.connect(self.area_changed)
        self.select_features_rectangle_tool.geometryEnded.connect(self.area_ended)
        self.select_features_freehand_tool.geometryChanged.connect(self.area_changed)
        self.select_features_freehand_tool.geometryEnded.connect(self.area_ended)
        self.select_features_tool.geometryChanged.connect(self.area_changed)
        self.select_features_tool.geometryEnded.connect(self.area_ended)

        self.nmpt_dockwidget.selectedAreaReset.clicked.connect(self.area_info_reset)
        self.nmpt_dockwidget.maxAreaReachedLabel.setVisible(False)
        self.nmpt_dockwidget.areaWidget.setHidden(True)

        self.nmpt_dockwidget.downloadButton.clicked.connect(self.download_nmpt)
        self.nmpt_dockwidget.downloadButton.setEnabled(False)

    def change_nmpt_dockwidget_visibility(self):

        if self.nmpt_dockwidget is None:
            self.init_nmpt_dockwidget()

        if not self.nmpt_dockwidget.isVisible():
            iface.addDockWidget(Qt.RightDockWidgetArea, self.nmpt_dockwidget)

        else:
            iface.removeDockWidget(self.nmpt_dockwidget)

    @update_download_button_state_dec
    def data_radiobutton_state(self, button):

        if button.isChecked() is True:

            if button.text() == "NMT Arc/Info ASCII Grid":
                self.nmpt_dockwidget.evrfRadioButton.setEnabled(True)
                self.data_format = "DigitalTerrainModel"

            if button.text() == "NMT GeoTIFF":
                self.nmpt_dockwidget.evrfRadioButton.setEnabled(False)
                self.nmpt_dockwidget.kronRadioButton.setChecked(True)
                self.data_format = "DigitalTerrainModelFormatTIFF"

            if button.text() == "NMPT":
                self.nmpt_dockwidget.evrfRadioButton.setEnabled(True)
                self.data_format = "DigitalSurfaceModel"

            if button.text() == "PL-KRON86-NH":
                self.datum_format = "KRON86"

            if button.text() == "PL-EVRF2007-NH":
                self.datum_format = "EVRF2007"

    def on_layer_changed(self):

        layer = self.nmpt_dockwidget.projectLayerList.currentLayer()

        if layer:
            if layer.dataProvider().featureCount() == 0:
                return
            self.source_layer = layer
            area = self.get_area_in_ha(self.source_layer.extent())
            self.area_changed(area)
            layer.selectionChanged.connect(self.on_layer_features_selection_changed)
            self.on_layer_features_selection_changed(layer.selectedFeatureIds())
            self.nmpt_dockwidget.selectedOnlyCheckBox.setEnabled(True)

        else:
            self.nmpt_dockwidget.selectedOnlyCheckBox.setEnabled(False)
            self.nmpt_dockwidget.selectedOnlyCheckBox.setChecked(False)
            self.source_layer = None
            self.nmpt_dockwidget.selectedOnlyCheckBox.setText("Tylko zaznaczone obiekty [0]")
            self.area_info_reset()

    def get_area_in_ha(self, bbox: QgsRectangle):

        bbox_geom = QgsGeometry.fromRect(bbox)
        if self.source_layer.crs() != QgsCoordinateReferenceSystem(2180):
            bbox_geom.transform(QgsCoordinateTransform(self.source_layer.crs(), QgsCoordinateReferenceSystem(2180), QgsProject.instance()))
        self.bbox = bbox_geom.boundingBox()
        area = QgsDistanceArea()
        area.setSourceCrs(QgsCoordinateReferenceSystem.fromEpsgId(2180), QgsCoordinateTransformContext())
        area.setEllipsoid('GRS80')
        rectangle_area = area.measureArea(bbox_geom)
        rectangle_area_hectares = area.convertAreaMeasurement(rectangle_area, QgsUnitTypes.AreaHectares)
        return rectangle_area_hectares

    def on_layer_features_selection_changed(self, selected_features):

        if self.nmpt_dockwidget.selectedOnlyCheckBox.isChecked():
            self.get_bbox_and_area_for_selected()

        self.nmpt_dockwidget.selectedOnlyCheckBox.setText(
            f"Tylko zaznaczone obiekty [{len(selected_features)}]")

    def get_bbox_and_area_for_selected(self):

        if self.nmpt_dockwidget.selectedOnlyCheckBox.isChecked():
            bbox = self.source_layer.boundingBoxOfSelected()

        else:
            bbox = self.source_layer.extent()

        area = self.get_area_in_ha(bbox)
        self.area_changed(area)

    def activateTool(self, tool):

        iface.mapCanvas().setMapTool(tool)

    @update_download_button_state_dec
    def area_changed(self, area: float):

        self.nmpt_dockwidget.areaWidget.setHidden(False)
        self.nmpt_dockwidget.selectedAreaLabel.setText(f"Powierzchnia: {round(area, 2)} ha")

        if area == 0:
            self.area_under_limit = False

        elif area > 1000:
            self.nmpt_dockwidget.maxAreaReachedLabel.setVisible(True)
            self.area_under_limit = False

        else:
            self.nmpt_dockwidget.maxAreaReachedLabel.setVisible(False)
            self.nmpt_dockwidget.selectedAreaLabel.setVisible(True)
            self.area_under_limit = True

    @update_download_button_state_dec
    def area_ended(self, _, geom: QgsGeometry):

        current_crs = QgsProject.instance().crs()
        crs_2180 = QgsCoordinateReferenceSystem.fromEpsgId(2180)

        if current_crs != crs_2180:
            transformation = QgsCoordinateTransform(current_crs, crs_2180, QgsProject.instance())
            geom.transform(transformation)

        self.bbox = geom.boundingBox()

    @update_download_button_state_dec
    def area_info_reset(self, *args, **kwargs):

        self.nmpt_dockwidget.maxAreaReachedLabel.setVisible(False)
        self.nmpt_dockwidget.areaWidget.setHidden(True)
        self.area_under_limit = True
        self.bbox = None
        self.nmpt_dockwidget.selectedAreaLabel.setText("Powierzchnia: 0 ha")
        self.selectRectangleTool.reset()
    

    def browse_filepath_for_nmpt(self):

        self.nmpt_filepath = QFileDialog.getExistingDirectory(self.nmpt_dockwidget,
                                                 'Wybierz miejsce zapisu NM(P)T',
                                                 expanduser("~"))
        self.nmpt_dockwidget.filepathLine.setText(self.nmpt_filepath)

    def download_nmpt(self):

        self.task = NMPTdownloadTask(
            "Pobieranie NM(P)T",
            self.data_format,
            self.datum_format,
            self.bbox,
            self.nmpt_filepath)
        self.task.download_filepath.connect(self.load_nmpt_to_project)
        manager = QgsApplication.taskManager()
        manager.addTask(self.task)

    def load_nmpt_to_project(self, filepath_and_layer_name: list):

        layer = QgsRasterLayer(*filepath_and_layer_name)
        layer.setCrs(QgsCoordinateReferenceSystem(2180))
        QgsProject.instance().addMapLayer(layer)
        iface.messageBar().pushWidget(QgsMessageBarItem("Wtyczka GIS Support",
                    "Pomyślnie pobrano NM(P)T", level=Qgis.Info))

import os
from urllib.request import urlopen

from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QKeySequence, QPixmap
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsCoordinateTransformContext, QgsMapLayerProxyModel,
                       QgsProject)
from qgis.gui import QgsMessageBarItem
from qgis.utils import iface

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), "main_base.ui"
))

CRS_2180 = QgsCoordinateReferenceSystem()
CRS_2180.createFromSrid(2180)

def get_obiekty_form(count):
    form = "obiekt"
    count = count
    if count == 1:
        pass
    elif 2 <= count <= 4:
        form = "obiekty"
    elif 5 <= count <= 20:
        form = "obiektów"
    else:
        units = count % 10
        if units in (2,3,4):
            form = "obiekty"
        else:
            form = "obiektów"
    return form

class UI(QtWidgets.QFrame, FORM_CLASS):

    icon_info_path = ':/plugins/plugin/info.png'

    def __init__(self, target_layout, parent = None):
        super().__init__(parent)

        self.setupUi(self)
        
        target_layout.layout().addWidget(self)

        self.layer_select.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        self.label_info_start.setPixmap(QPixmap(self.icon_info_path))
        self.label_info_start.setToolTip((
            "Sprawdzanie wielu obiektów może być czasochłonne. W tym czasie\n"
            "będziesz mógł korzystać z pozostałych funkcjonalności wtyczki,\n"
            "ale mogą one działać wolniej. Sprawdzanie obiektów działa również\n"
            "po zamknięciu wtyczki."))
        
        self.label_info_percent.setPixmap(QPixmap(self.icon_info_path))
        self.label_info_percent.setToolTip((
            "Narzędzie porównuje pole powierzchni działek.\n"
            "Parametr dokładności określa dopuszczalny % różnicy\n"
            "np. parametr 1% ignoruje różnicę powierzchni mniejszą niż 1%"))   

        self.frame_how_it_works.setToolTip((
            "Narzędzie sprawdza dopasowanie geometrii warstwy źródłowej do obiektów w ULDK."))   
        self.label_info_icon.setPixmap(QPixmap(self.icon_info_path))

class CheckLayer:

    def __init__(self, parent, target_layout):
        self.parent = parent
        self.canvas = iface.mapCanvas()
        self.ui = UI(target_layout)
        self.__init_ui()


    def __init_ui(self):
        # self.ui.button_start.clicked.connect(self.search)
        # self.ui.button_cancel.clicked.connect(self.__stop)
        self.__on_layer_changed(self.ui.layer_select.currentLayer())
        self.ui.layer_select.layerChanged.connect(self.__on_layer_changed)
        self.ui.label_status.setText("")
        self.ui.label_found_count.setText("")
        self.ui.label_not_found_count.setText("")


    def __on_layer_changed(self, layer):
        self.ui.button_start.setEnabled(False)
        if layer:
            if layer.dataProvider().featureCount() == 0:
                return
            self.source_layer = layer
            layer.selectionChanged.connect(self.__on_layer_features_selection_changed)
            self.ui.button_start.setEnabled(True)
            current_layer_name = layer.sourceName()
            suggested_target_layer_name = f"{current_layer_name} - Działki ULDK"
            self.ui.text_edit_target_layer_name.setText(suggested_target_layer_name)
            self.ui.button_start.setEnabled(True)
        else:
            self.source_layer = None
            self.ui.text_edit_target_layer_name.setText("")
            self.ui.checkbox_selected_only.setText("Tylko zaznaczone obiekty [0]")

    def __on_layer_features_selection_changed(self, selected_features):
        if not self.source_layer:
            selected_features = []
        self.ui.checkbox_selected_only.setText(f"Tylko zaznaczone obiekty [{len(selected_features)}]")
import os

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QFrame
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.utils import iface
from qgis.core import QgsMapLayerProxyModel

from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR

class DropFrame(QFrame):
    """
    Customowa klasa ramki ogarniająca przeciąganie i upuszczanie plików gpkg
    """

    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith('.gpkg'):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.gpkg'):
                self.file_dropped.emit(file_path)
                return
        iface.messageBar().pushCritical("Usemaps Lite", TRANSLATOR.translate_error("wrong file format"))

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'import_layer.ui'))


class ImportLayerDialog(QDialog, FORM_CLASS):
    """
    Dialog wgrywania warstw GPKG do organizacji
    """

    def __init__(self):
        super(ImportLayerDialog, self).__init__(parent=iface.mainWindow())
        self.setupUi(self)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.layer_combobox.setFilters(QgsMapLayerProxyModel.VectorLayer)

        self.cancel_button.clicked.connect(self.hide)

    def showEvent(self, event):
        super().showEvent(event)
        self.layer_combobox.setVisible(True)
        self.layer_label.setVisible(True)
        self.add_button.setVisible(True)

        self.setWindowTitle(TRANSLATOR.translate_ui("import layer title"))
        self.layer_label.setText(TRANSLATOR.translate_ui("layer_label"))
        self.add_button.setText(TRANSLATOR.translate_ui("add"))
        self.cancel_button.setText(TRANSLATOR.translate_ui("cancel"))



from PyQt5 import uic
from PyQt5 import QtWidgets
import os

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'wmts_cache_dialog.ui'))

class WMTSCacheDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(WMTSCacheDialog, self).__init__(parent)
        self.setupUi(self)

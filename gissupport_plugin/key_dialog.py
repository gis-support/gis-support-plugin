import os

from PyQt5 import uic
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QDialog

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'key_dialog.ui'))


class GisSupportPluginDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(GisSupportPluginDialog, self).__init__(parent)
        self.setupUi(self)
        self.saveKeyButton.clicked.connect(self.saveKey)

    def show(self):
        self.keyLineEdit.setText(QSettings().value('gissupport/api/key'))
        super().show()

    def saveKey(self):
        key = self.keyLineEdit.text().strip()
        QSettings().setValue('gissupport/api/key', key)
        self.hide()

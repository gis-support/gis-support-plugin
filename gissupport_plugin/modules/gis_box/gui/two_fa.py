#coding: utf-8
import os

from PyQt5.QtCore import pyqtSignal
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'two_fa.ui'))


class TwoFADialog(QDialog, FORM_CLASS):

    def __init__(self, parent, parents=None):
        super(TwoFADialog, self).__init__(parents)
        self.setupUi(self)

        self.edCode.setInputMask("999999;_")
        self.edCode.clear()

        self.verification_code = ""

        self.buttonBox.accepted.connect(self.dialogAccepted)
        self.buttonBox.rejected.connect(self.dialogRejected)

    def dialogAccepted(self):
        code = self.edCode.displayText()
        self.verification_code = code
        self.close()

    def dialogRejected(self):
        self.close()

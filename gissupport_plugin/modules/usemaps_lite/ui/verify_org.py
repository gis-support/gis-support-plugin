import os

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.utils import iface
from qgis.PyQt.QtCore import Qt

from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'verify_org.ui'))


class VerifyOrgDialog(QDialog, FORM_CLASS):
    """
    Dialog związany z weryfikacją w trakcie rejestracji.
    """

    def __init__(self):
        super(VerifyOrgDialog, self).__init__(parent=iface.mainWindow())
        self.setupUi(self)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self.cancel_button.clicked.connect(self.hide)
        self.code_line.textChanged.connect(self.verify_code)

    def showEvent(self, event):
        super().showEvent(event)
        self.code_line.clear()

        self.setWindowTitle(TRANSLATOR.translate_ui("verify org title"))
        self.verify_label.setText(TRANSLATOR.translate_ui("verify_label"))
        self.code_line.setPlaceholderText(TRANSLATOR.translate_ui("code_line"))
        self.verify_button.setText(TRANSLATOR.translate_ui("ok"))
        self.cancel_button.setText(TRANSLATOR.translate_ui("cancel"))

    def verify_code(self, code: str):
        """
        Sprawdza, czy podany kod:
        1. zawiera 6 znaków (zakodowaliśmy w dialogu maksymalną długość na 6, ale nie moze mieć i tak mniej)
        2. kazdy znak to liczba
        """

        self.verify_button.setEnabled(False)
        if code.isdigit() and len(code) == 6:
            self.verify_button.setEnabled(True)

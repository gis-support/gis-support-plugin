import os

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.utils import iface
from qgis.PyQt.QtCore import Qt

from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'forgot_password.ui'))


class ForgotPasswordDialog(QDialog, FORM_CLASS):
    """
    Dialog resetu hasła konta Usemaps Lite.
    """

    def __init__(self):
        super(ForgotPasswordDialog, self).__init__(parent=iface.mainWindow())
        self.setupUi(self)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.cancel_button.clicked.connect(self.hide)

    def showEvent(self, event):
        super().showEvent(event)

        self.setWindowTitle(TRANSLATOR.translate_ui("reset pwd title"))
        self.reset_pwd_info_label.setText(TRANSLATOR.translate_ui("reset_pwd_info_label"))
        self.reset_button.setText(TRANSLATOR.translate_ui("reset_button"))
        self.cancel_button.setText(TRANSLATOR.translate_ui("cancel"))


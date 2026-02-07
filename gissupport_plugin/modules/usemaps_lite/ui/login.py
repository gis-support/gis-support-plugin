import os

from qgis.core import QgsSettings
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog
from qgis.utils import iface

from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'login.ui'))


class LoginDialog(QDialog, FORM_CLASS):
    """
    Dialog logowania do Usemaps Lite.
    """

    def __init__(self):
        super(LoginDialog, self).__init__(parent=iface.mainWindow())
        self.setupUi(self)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.cancel_button.clicked.connect(self.hide)

    def showEvent(self, event):
        super().showEvent(event)

        self.setWindowTitle(TRANSLATOR.translate_ui("login title"))
        self.email_label.setText(TRANSLATOR.translate_ui("email_label"))
        self.password_label.setText(TRANSLATOR.translate_ui("password_label"))
        self.login_button.setText(TRANSLATOR.translate_ui("login_button"))
        self.cancel_button.setText(TRANSLATOR.translate_ui("cancel"))
        self.forgot_pwd_button.setText(TRANSLATOR.translate_ui("forgot_pwd_button"))

        settings = QgsSettings()
        username = settings.value("usemaps_lite/login", "", type=str)
        pwd = settings.value("usemaps_lite/pwd", "", type=str)
        
        if username and pwd:
            self.log_email_line.setText(username)
            self.log_pwd_line.setText(pwd)
        else:
            self.log_email_line.clear()
            self.log_pwd_line.clear()

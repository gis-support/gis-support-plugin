import os

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.utils import iface
from qgis.PyQt.QtCore import Qt

from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR
from gissupport_plugin.tools.usemaps_lite.validators import validate_email

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'register.ui'))


class RegisterDialog(QDialog, FORM_CLASS):
    """
    Dialog rejestracji usera i organizacji
    """

    def __init__(self):
        super(RegisterDialog, self).__init__(parent=iface.mainWindow())
        self.setupUi(self)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.cancel_button.clicked.connect(self.hide)

        self.reg_email_line.textChanged.connect(self.handle_register_button)
        self.reg_orgname_line.textChanged.connect(self.handle_register_button)
        self.reg_pwd_line.textChanged.connect(self.handle_register_button)
        self.reg_pwd_again_line.textChanged.connect(self.handle_register_button)

        self.terms_checkbox.stateChanged.connect(self.handle_register_button)
        
        self.reg_register_button.setEnabled(False)

    def showEvent(self, event):
        super().showEvent(event)
        self.reg_email_line.clear()
        self.reg_orgname_line.clear()
        self.reg_pwd_line.clear()
        self.reg_pwd_again_line.clear()

        self.setWindowTitle(TRANSLATOR.translate_ui("register title"))
        self.orgname_label.setText(TRANSLATOR.translate_ui("orgname_label"))
        self.reg_email_label.setText(TRANSLATOR.translate_ui("reg_email_label"))
        self.password_label.setText(TRANSLATOR.translate_ui("password_label"))
        self.password_again_label.setText(TRANSLATOR.translate_ui("password_again_label"))
        self.reg_register_button.setText(TRANSLATOR.translate_ui("reg_register_button"))
        self.cancel_button.setText(TRANSLATOR.translate_ui("cancel"))
        self.password_hint_label.setText(TRANSLATOR.translate_ui("password_hint_label"))
        self.terms_label.setText(TRANSLATOR.translate_ui("terms_checkbox"))
        self.terms_checkbox.setText("")

    def handle_register_button(self):

        enabled = False
        if self.reg_pwd_line.text() and self.reg_pwd_again_line.text() and self.reg_orgname_line.text() and self.reg_email_line.text() and validate_email(self.reg_email_line.text()) and self.terms_checkbox.isChecked():
            enabled = True

        self.reg_register_button.setEnabled(enabled)

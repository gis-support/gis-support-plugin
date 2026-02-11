import os

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.utils import iface
from qgis.PyQt.QtCore import Qt

from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR
from gissupport_plugin.tools.usemaps_lite.validators import validate_email

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'invite_user.ui'))


class InviteUserDialog(QDialog, FORM_CLASS):
    """
    Dialog zapraszania ludzi do organizacji.
    """

    def __init__(self):
        super(InviteUserDialog, self).__init__(parent=iface.mainWindow())
        self.setupUi(self)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self.cancel_button.clicked.connect(self.hide)
        self.email_line.textChanged.connect(self.toggle_invite_user_button)

    def showEvent(self, event):
        super().showEvent(event)
        self.email_line.clear()
        self.invite_user_button.setEnabled(False)

        self.setWindowTitle(TRANSLATOR.translate_ui("invite user title"))
        self.label.setText(TRANSLATOR.translate_ui("invite user label"))
        self.email_label.setText(TRANSLATOR.translate_ui("email_label"))
        self.invite_user_button.setText(TRANSLATOR.translate_ui("invite"))
        self.cancel_button.setText(TRANSLATOR.translate_ui("cancel"))

    def toggle_invite_user_button(self, email: str):
        
        self.invite_user_button.setEnabled(validate_email(email))

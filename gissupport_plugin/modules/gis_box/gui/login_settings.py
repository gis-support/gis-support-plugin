#coding: utf-8
import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import QDialog

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'login_settings.ui'))


class LoginSettingsDialog(QDialog, FORM_CLASS):
    def __init__(self, parent, parents=None):
        super(LoginSettingsDialog, self).__init__(parents)
        self.setupUi(self)

        # Ustawienia logowania
        settings = QSettings()
        settings.beginGroup('gissupport/gisbox_connection')
        settings.setValue('user', settings.value('user', 'DEMO'))
        settings.setValue('pass', settings.value('pass', 'JesliChceszEdytowacNapiszDoNas:)'))
        settings.setValue('host', settings.value('host', 'https://demo.gisbox.pl'))
        
        self.leLogin.setText(settings.value('user', 'DEMO'))
        self.leLogin.textChanged.connect(
            lambda text: settings.setValue('user', text))
        self.lePassword.setText(settings.value('pass', 'JesliChceszEdytowacNapiszDoNas:)'))
        self.lePassword.textChanged.connect(
            lambda text: settings.setValue('pass', text))
        self.leHost.setText(settings.value('host', 'https://demo.gisbox.pl'))
        self.leHost.textChanged.connect(
            lambda text: settings.setValue('host', text))

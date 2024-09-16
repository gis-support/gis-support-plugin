#coding: utf-8
import json
import os

from PyQt5.QtCore import pyqtSignal, QSettings, QUrl
from PyQt5.QtNetwork import QNetworkRequest
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsNetworkAccessManager
from qgis.core import Qgis
from qgis.utils import iface

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'two_fa.ui'))


class TwoFADialog(QDialog, FORM_CLASS):

    def __init__(self, parents=None):
        super(TwoFADialog, self).__init__(parents)
        self.setupUi(self)

        self.edCode.setInputMask("999999;_")
        self.edCode.clear()

        self.verification_code = ""

        self.buttonBox.accepted.connect(self.dialogAccepted)
        self.buttonBox.rejected.connect(self.dialogRejected)
        self.btSendAgain.clicked.connect(self.resendCode)

    def closeEvent(self, event):
        self.edCode.clear()
        self.close()

    def dialogAccepted(self):
        code = self.edCode.displayText()
        self.verification_code = code
        self.edCode.clear()
        self.accept()

    def dialogRejected(self):
        self.edCode.clear()
        self.close()

    def resendCode(self):
        settings = QSettings()
        settings.beginGroup('gissupport/gisbox_connection')

        host = settings.value('host')
        endpoint = '/api/login'
        payload = {
            'data': {
                'username_or_email': settings.value('user'),
                'password': settings.value('pass')
            }
        }

        manager = QgsNetworkAccessManager()
        request = QNetworkRequest(QUrl(host + endpoint))
        request.setHeader(QNetworkRequest.ContentTypeHeader, 'application/json')
        request.setHeader(QNetworkRequest.UserAgentHeader, 'qgis')

        data = json.dumps(payload).encode('utf-8')

        manager.blockingPost(request, data)

        iface.messageBar().pushMessage(
            'Weryfikacja dwuetapowa',
            'Wysłano kod weryfikacyjny ponownie.',
            level=Qgis.Info
        )


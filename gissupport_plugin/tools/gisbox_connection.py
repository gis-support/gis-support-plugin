# coding: utf-8
import uuid
from PyQt5.QtCore import QObject, QUrl, pyqtSignal, QSettings
from PyQt5.QtNetwork import QNetworkRequest
from qgis.core import QgsNetworkAccessManager, Qgis
import json

from .logger import Logger
from ..modules.gis_box.gui.two_fa import TwoFADialog


class GisboxConnection(QObject, Logger):
    on_connect = pyqtSignal(bool)
    on_disconnect = pyqtSignal()
    on_error = pyqtSignal(dict)

    MANAGER = QgsNetworkAccessManager()
    MANAGER.setTimeout(600000)
    QUEUE = {}

    def __init__(self, parent=None):
        super(GisboxConnection, self).__init__()
        self.parent = parent

        self.token = None
        self.host = None
        self.is_connected = False

        self.twoFaDialog = None

    @classmethod
    def _exec_callback(cls, uuid_: str):
        reply, callback = cls.QUEUE[uuid_]

        try:
            response_data = json.loads(bytearray(reply.readAll()))
        except Exception as e:
            cls.message(f'Błąd komunikacji z API: {e}', level=Qgis.Critical, duration=5)
            return

        status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

        if status_code not in (200, 201, 204):
            error_message = response_data['error_message']
            cls.message(f'{error_message}', level=Qgis.Critical, duration=5)
            return

        callback(response_data)
        del cls.QUEUE[uuid_]

    @staticmethod
    def generate_random_uuid():
        return str(uuid.uuid4())

    def _getHost(self):
        settings = QSettings()
        settings.beginGroup('gissupport/gisbox_connection')
        host = settings.value('host')
        self.host = host
        return host

    def authenticate(self) -> bool:
        """ Logowanie za pomocą REST API """
        request = self._createRequest('/api/login', with_token=False)
        settings = QSettings()
        settings.beginGroup('gissupport/gisbox_connection')
        payload = {
            'data': {
                'username_or_email': settings.value('user'),
                'password': settings.value('pass')
            }
        }
        reply = self.MANAGER.blockingPost(request, json.dumps(payload).encode('utf-8'))
        response_raw = bytearray(reply.content())
        status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if not response_raw:
            self.message(
                'Błąd połączenia z serwerem. Sprawdź czy adres aplikacji jest prawidłowy lub skontaktuj się z administratorem',
                level=Qgis.Critical, duration=5)
            return False
        response = json.loads(response_raw)
        if status_code != 200 and status_code != 201:
            error_message = response.get('error_message')
            self.message(f'{error_message}', level=Qgis.Critical, duration=5)
            return False

        if status_code == 201:
            if self.twoFaDialog is None:
                self.twoFaDialog = TwoFADialog()

            dialog = self.twoFaDialog.exec()
            if dialog != 0:
                return self.verify_code(self.twoFaDialog.verification_code)
            else:
                return False

        else:
            self.token = response['token']
            return True

    def connect(self) -> bool:
        if self.authenticate():
            self.log("Połączono")
            self.on_connect.emit(True)
            self.is_connected = True
            return True
        self.on_disconnect.emit()
        return False

    def disconnect(self):
        self.log("Rozłączono")
        self.on_disconnect.emit()
        self.is_connected = False
        return True

    def _createRequest(self, endpoint: str, content_type: str = 'application/json',
                       with_token: bool = True) -> QNetworkRequest:
        host = self._getHost()
        request = QNetworkRequest(QUrl(host + endpoint))
        request.setHeader(QNetworkRequest.ContentTypeHeader, content_type)
        request.setHeader(QNetworkRequest.UserAgentHeader, 'qgis')
        if with_token:
            request.setRawHeader(b'X-Access-Token', bytes(self.token.encode()))

        return request

    def get(self, endpoint: str, sync: bool = False, callback: any = None):
        request = self._createRequest(endpoint)

        if sync:
            reply = self.MANAGER.blockingGet(request)

            response = json.loads(bytearray(reply.content()))
            return response

        reply = self.MANAGER.get(request)

        if callback:
            random_uuid = self.generate_random_uuid()
            self.QUEUE[random_uuid] = (reply, callback)
            reply.finished.connect(lambda: self._exec_callback(random_uuid))

        return reply
    
    def post(self, endpoint: str, payload: dict, callback: any = None, srid: str = None):
        request = self._createRequest(endpoint)
        if srid:
            request.setRawHeader(b'X-Response-SRID', srid.encode())

        data = json.dumps(payload).encode()

        reply = self.MANAGER.post(request, data)
        response = reply.readAll()

        if callback:
            random_uuid = self.generate_random_uuid()
            self.QUEUE[random_uuid] = (reply, callback)
            reply.finished.connect(lambda: self._exec_callback(random_uuid))

        return response

    def verify_code(self, code: int):
        settings = QSettings()
        settings.beginGroup('gissupport/gisbox_connection')
        payload = {
            'data': {
                'username_or_email': settings.value('user'),
                'password': settings.value('pass'),
                'verification_code': code
            }
        }
        request = self._createRequest('/api/login', with_token=False)
        reply = self.MANAGER.blockingPost(request, json.dumps(payload).encode('utf-8'))
        response_raw = bytearray(reply.content())
        status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if not response_raw:
            self.message(
                'Błąd połączenia z serwerem. Sprawdź czy adres aplikacji jest prawidłowy lub skontaktuj się z administratorem',
                level=Qgis.Critical, duration=5)
            return False
        response = json.loads(response_raw)
        if status_code != 200:
            error_message = response.get('error_message')
            self.message(f'{error_message}', level=Qgis.Critical, duration=5)
            return False
        else:
            self.token = response['token']
            return True


GISBOX_CONNECTION = GisboxConnection()
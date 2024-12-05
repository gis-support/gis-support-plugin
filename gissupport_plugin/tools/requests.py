import json
from typing import Union

from qgis.core import QgsNetworkAccessManager
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply
from PyQt5.QtCore import QCoreApplication, QUrl
from qgis.PyQt.QtCore import QObject, pyqtSignal

from urllib.parse import urlencode


class NetworkHandler(QObject):
    downloadProgress: pyqtSignal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.network_manager = QgsNetworkAccessManager.instance()
        self.result = None

    def handle_response(self, reply, retry_callback=None, reply_only: bool=False):
        if reply_only:
            self.result = reply
            return
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll().data().decode()
            self.result = {'data': data}
        else:
            if retry_callback:
                self.error_occurred = True
                retry_callback()
            elif reply.error() in (QNetworkReply.TimeoutError, QNetworkReply.OperationCanceledError, QNetworkReply.UnknownServerError):
                self.result = {'error': reply.errorString(), 'msg': 'Przekroczono czas oczekiwania na odpowiedź serwera.'}
            else:
                self.result = {'error': reply.errorString()}

    def get(self, url, reply_only: bool=False, params: dict=None) -> Union[dict, QNetworkReply]:
        """Wykonuje żądanie GET do podanego URL"""
        self.result = None
        self.error_occurred = False

        def try_request(url, retry_callback=None):
            request = QNetworkRequest(QUrl(url))
            
            reply = self.network_manager.get(request)
            reply.downloadProgress.connect( lambda recv, total: self.downloadProgress.emit( int(100*recv/total) ) )
            reply.finished.connect(lambda: self.handle_response(reply, retry_callback, reply_only))
            return reply

        if params:
            url += "?" + urlencode(params)

        reply = try_request(url)

        app = QCoreApplication.instance()
        while self.result is None and not reply.isFinished():
            app.processEvents()

        return self.result

    def post(self, url, reply_only: bool = False, params: dict = None, data: dict = None, srid: str = None, databox: bool = False) -> Union[dict, QNetworkReply]:
        """Wykonuje żądanie POST do podanego URL"""
        self.result = None
        self.error_occurred = False

        def try_request(url, body, srid: str = None, retry_callback=None):
            request = QNetworkRequest(QUrl(url))
            if srid:
                request.setRawHeader(b'X-Response-SRID', srid.encode())
            if databox:
                request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
            reply = self.network_manager.post(request, body)
            reply.downloadProgress.connect( lambda recv, total: self.downloadProgress.emit( int(100*recv/total) ) )
            reply.finished.connect(lambda: self.handle_response(reply, retry_callback, reply_only))
            return reply

        if params:
            url += "?" + urlencode(params)

        if data:
            data = str.encode(json.dumps(data))
        else:
            data = b''

        reply = try_request(url, data, srid)

        app = QCoreApplication.instance()
        while self.result is None and not reply.isFinished():
            app.processEvents()

        return self.result

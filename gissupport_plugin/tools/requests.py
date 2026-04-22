import json
from typing import Union

from qgis.core import QgsNetworkAccessManager
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.PyQt.QtCore import QCoreApplication, QUrl
from qgis.PyQt.QtCore import QObject, pyqtSignal

from urllib.parse import urlencode
import ssl
from urllib.request import Request, urlopen

from gissupport_plugin.tools.gisbox_connection import GISBOX_CONNECTION


class LegacyQNetworkReplyMock:
    def __init__(self, data: bytes, err: str = ""):
        self._d = data
        self._err = err
        
    def error(self):
        return QNetworkReply.NetworkError.NoError if not self._err else QNetworkReply.NetworkError.UnknownNetworkError
    
    def header(self, _):
        return len(self._d)
    
    def readAll(self):
        class ByteArrayMock:
            def data(slf): return self._d
        return ByteArrayMock()

def legacy_network_get(url: str):
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.options |= 0x4
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urlopen(req, context=ctx, timeout=15)
        return LegacyQNetworkReplyMock(res.read())
    except Exception as e:
        return LegacyQNetworkReplyMock(b'', str(e))

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
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll().data().decode()
            self.result = {'data': data}
        else:
            if retry_callback:
                self.error_occurred = True
                retry_callback()
            elif reply.error() in (QNetworkReply.NetworkError.TimeoutError, QNetworkReply.NetworkError.OperationCanceledError, QNetworkReply.NetworkError.UnknownServerError):
                self.result = {'error': reply.errorString(), 'msg': 'Przekroczono czas oczekiwania na odpowiedź serwera.'}
            elif reply.error() == QNetworkReply.NetworkError.ContentAccessDenied:
                self.result = {'error': reply.errorString(), 'msg': 'Przekroczono limit danych. Zmniejsz wskazany obszar.'}
            else:
                if (status_code := reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)) == 400 and (
                        detail := json.loads(bytearray(reply.readAll())).get("detail")):
                    self.result = {'error': reply.errorString(), 'details': detail}
                else:
                    self.result = {'error': reply.errorString()}

    def get(self, url, reply_only: bool=False, params: dict=None) -> Union[dict, QNetworkReply]:
        """Wykonuje żądanie GET do podanego URL"""
        self.result = None
        self.error_occurred = False

        if "geoportal" in url or "gugik.gov.pl" in url:
            return legacy_network_get(url)

        def try_request(url, retry_callback=None):
            request = QNetworkRequest(QUrl(url))
            
            reply = self.network_manager.get(request)
            reply.downloadProgress.connect( lambda recv, total: self.downloadProgress.emit(self.set_progress(recv, total)))
            reply.finished.connect(lambda: self.handle_response(reply, retry_callback, reply_only))
            return reply

        if params:
            url += "?" + urlencode(params)

        reply = try_request(url)

        app = QCoreApplication.instance()
        while self.result is None and not reply.isFinished():
            app.processEvents()

        return self.result

    def post(self, url, reply_only: bool = False, params: dict = None, data: dict = None, srid: str = None, databox: bool = False, token: bool = False) -> Union[dict, QNetworkReply]:
        """Wykonuje żądanie POST do podanego URL"""
        self.result = None
        self.error_occurred = False

        def try_request(url, body, srid: str = None, retry_callback=None, token: bool = False):
            request = QNetworkRequest(QUrl(url))
            if srid:
                request.setRawHeader(b'X-Response-SRID', srid.encode())
            if token:
                request.setRawHeader(b'X-User-Agent', b'qgis_gs')
                request.setRawHeader(b'X-Access-Token', GISBOX_CONNECTION.token.encode())
            if databox:
                request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
            reply = self.network_manager.post(request, body)
            reply.downloadProgress.connect( lambda recv, total: self.downloadProgress.emit(self.set_progress(recv, total)))
            reply.finished.connect(lambda: self.handle_response(reply, retry_callback, reply_only))
            return reply

        if params:
            url += "?" + urlencode(params)

        if data:
            data = str.encode(json.dumps(data))
        else:
            data = b''

        reply = try_request(url, data, srid, token=token)

        app = QCoreApplication.instance()
        while self.result is None and not reply.isFinished():
            app.processEvents()

        return self.result

    def set_progress(self, recv, total):

        if total == 0:
            return 0
        return int(100*recv/total)

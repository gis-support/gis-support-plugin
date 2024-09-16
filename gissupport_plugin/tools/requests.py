from typing import Union

from qgis.core import QgsNetworkAccessManager
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply
from PyQt5.QtCore import QCoreApplication, QUrl
from qgis.PyQt.QtCore import QObject

from urllib.parse import urlencode


class NetworkHandler(QObject):
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
            else:
                self.result = {'error': reply.errorString()}

    def get(self, url, reply_only: bool=False, params: dict=None) -> Union[dict, QNetworkReply]:
        """Wykonuje żądanie GET do podanego URL"""
        self.result = None
        self.error_occurred = False

        def try_request(url, retry_callback=None):
            request = QNetworkRequest(QUrl(url))
            
            reply = self.network_manager.get(request)
            reply.finished.connect(lambda: self.handle_response(reply, retry_callback, reply_only))
            return reply

        if params:
            url += "?" + urlencode(params)

        reply = try_request(url)

        app = QCoreApplication.instance()
        while self.result is None and not reply.isFinished():
            app.processEvents()

        return self.result
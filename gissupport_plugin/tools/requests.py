from qgis.core import QgsNetworkAccessManager
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply
from PyQt5.QtCore import QCoreApplication, QUrl
from qgis.PyQt.QtCore import QObject


class NetworkHandler(QObject):
    def __init__(self):
        super().__init__()
        self.network_manager = QgsNetworkAccessManager.instance()
        self.result = None

    def handle_response(self, reply, retry_callback=None):
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll().data().decode()
            self.result = {'data': data}
        else:
            if retry_callback:
                self.error_occurred = True
                retry_callback()
            else:
                self.result = {'error': reply.errorString()}

    def get(self, url):
        """Wykonuje żądanie GET do podanego URL"""
        self.result = None
        self.error_occurred = False

        def try_request(url, retry_callback=None):
            request = QNetworkRequest(QUrl(url))
            reply = self.network_manager.get(request)
            reply.finished.connect(lambda: self.handle_response(reply, retry_callback))
            return reply

        reply = try_request(url)

        app = QCoreApplication.instance()
        while self.result is None and not reply.isFinished():
            app.processEvents()

        return self.result
import json
import os
import uuid
from typing import Union

from qgis.core import QgsNetworkAccessManager
from qgis.PyQt.QtCore import (
    QByteArray,
    QEventLoop,
    QFile,
    QIODevice,
    QObject,
    QTimer,
    QUrl,
    pyqtSignal,
)
from qgis.PyQt.QtNetwork import (
    QHttpMultiPart,
    QHttpPart,
    QNetworkReply,
    QNetworkRequest,
)

from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR


class ApiClient(QObject):
    """
    Osobna klasa do wykonywania requestów dla modułu Usemaps Lite, powstała na bazie pierwotnej klasy NetworkHandler.
    Jako że moduł Usemaps Lite posiada dedykowane metody do korzystania z SSE, po przeniesieniu kodu z repozytorium
    wtyczki Usemaps Lite klasa pozostała osobno.
    """

    event_received = pyqtSignal(str, object)

    def __init__(self):
        super().__init__()
        self.base_url = "https://usemaps-lite.gis.support/api/"
        self.auth_token = None
        self.nam = QgsNetworkAccessManager.instance()
        self._pending_callbacks = {}
    
        self._sse_reply = None
        self._sse_reconnect_timer = QTimer(self)
        self._sse_reconnect_timer.setSingleShot(True)
        self._sse_reconnect_timer.timeout.connect(self._reconnect_sse)
        self._sse_reconnect_delay = 1000
        self._sse_max_reconnect_delay = 30000
        self._is_sse_listening_requested = False

    def _make_request(self, endpoint, method="GET", data=None, callback=None) -> None:
        """
        Bazowa funkcja do wykonywania requestów.
        """

        url = QUrl(self.base_url + endpoint)
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

        if self.auth_token:
            request.setRawHeader(b"Authorization", f"Bearer {self.auth_token}".encode("utf-8"))

        request_id = str(uuid.uuid4())
        if callback:
            self._pending_callbacks[request_id] = callback

        if method == "GET":
            reply = self.nam.get(request)
        elif method == "POST":
            json_data = QByteArray(json.dumps(data).encode("utf-8"))
            reply = self.nam.post(request, json_data)
        elif method == "DELETE":
            json_data = QByteArray(json.dumps(data).encode("utf-8")) if data else QByteArray()
            reply = self.nam.sendCustomRequest(request, QByteArray(b"DELETE"), json_data)

        reply.setProperty("request_id", request_id)
        reply.setProperty("endpoint", endpoint)
        reply.finished.connect(lambda: self._handle_response(reply))

    def _handle_response(self, reply) -> None:
        """
        Funkcja do przetwarzania otrzymanej odpowiedzi z requesta.
        """

        request_id = reply.property("request_id")
        callback = self._pending_callbacks.pop(request_id, None)
        response_data = {}

        if reply.error() != QNetworkReply.NoError:
            error_msg_raw = reply.readAll().data().decode('utf-8', errors='ignore')
            parsed_error = {"error": reply.errorString(), "details": error_msg_raw}
            try:
                json_error = json.loads(error_msg_raw).get("error", TRANSLATOR.translate_error('api error'))
                if json_error:
                    parsed_error["server_message"] = json_error
            except json.JSONDecodeError:
                pass
            
            response_data["error"] = parsed_error

        else:
            content = reply.readAll().data().decode('utf-8', errors='ignore')
            try:
                parsed_content = json.loads(content)
            except json.JSONDecodeError:
                parsed_content = {"raw_response": content, "message": "Invalid JSON response from server."}
            response_data["data"] = parsed_content

        self.result = response_data
        if callback:
            callback(response_data)
        reply.deleteLater()

    def get(self, endpoint, callback=None) -> None:
        """
        Funkcja do wykonywania requestów GET
        """
        self._make_request(endpoint, method="GET", callback=callback)

    def post(self, endpoint, data, callback=None) -> None:
        """
        Funkcja do wykonywania requestów POST
        """
        self._make_request(endpoint, method="POST", data=data, callback=callback)
    
    def delete(self, endpoint, data, callback=None) -> None:
        """
        Funkcja do wykonywania requestów DELETE
        """
        self._make_request(endpoint, method="DELETE", data=data, callback=callback)

    def post_file(self, endpoint, file_path, callback=None) -> None:
        """
        Funkcja do wykonywania requestów POST z przesyłaniem pliku
        """
        url = QUrl(self.base_url + endpoint)
        request = QNetworkRequest(url)

        if self.auth_token:
            request.setRawHeader(b"Authorization", f"Bearer {self.auth_token}".encode("utf-8"))

        multi_part = QHttpMultiPart(QHttpMultiPart.FormDataType)

        file_part = QHttpPart()
        file_part.setHeader(QNetworkRequest.ContentDispositionHeader,
                            f'form-data; name="file"; filename="{os.path.basename(file_path)}"')

        file_part.setHeader(QNetworkRequest.ContentTypeHeader, "application/octet-stream")
        file = QFile(file_path)

        if not file.open(QIODevice.ReadOnly):
            if callback:
                callback({"error": f"Nie udało się otworzyć pliku: {file_path}"})
            return

        file_part.setBodyDevice(file)
        file.setParent(multi_part)
        multi_part.append(file_part)

        request_id = str(uuid.uuid4())
        if callback:
            self._pending_callbacks[request_id] = callback

        reply = self.nam.post(request, multi_part)
        reply.setProperty("request_id", request_id)
        reply.setProperty("endpoint", endpoint)
        reply.finished.connect(lambda: self._handle_response(reply))

        multi_part.setParent(reply)

    def simple_get(self, url) -> Union[dict, QNetworkReply]:
        """Wykonuje synchroniczny request GET"""
        self.result = None
        self.error_occurred = False

        def try_request(url):

            url = QUrl(self.base_url + url)
            request = QNetworkRequest(url)

            request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

            if self.auth_token:
                request.setRawHeader(b"Authorization", f"Bearer {self.auth_token}".encode("utf-8"))

            reply = self.nam.get(request)

            # reply.downloadProgress.connect( lambda recv, total: self.downloadProgress.emit(self.set_progress(recv, total)))
            reply.finished.connect(lambda: self._handle_response(reply))
            return reply

        reply = try_request(url)

        loop = QEventLoop()
        reply.finished.connect(loop.quit)
        loop.exec()

        return self.result

    def simple_post_file(self, endpoint, file_path) -> Union[dict, QNetworkReply]:
        """
        Wykonuje synchroniczny request POST z przesyłaniem pliku.
        """
        self.result = None
        self.error_occurred = False

        url = QUrl(self.base_url + endpoint)
        request = QNetworkRequest(url)

        if self.auth_token:
            request.setRawHeader(b"Authorization", f"Bearer {self.auth_token}".encode("utf-8"))

        multi_part = QHttpMultiPart(QHttpMultiPart.FormDataType)

        file_part = QHttpPart()
        file_part.setHeader(QNetworkRequest.ContentDispositionHeader,
                            f'form-data; name="file"; filename="{os.path.basename(file_path)}"')
        file_part.setHeader(QNetworkRequest.ContentTypeHeader, "application/octet-stream")

        file = QFile(file_path)
        if not file.open(QIODevice.ReadOnly):
            return {"error": f"Nie udało się otworzyć pliku: {file_path}"}

        file_part.setBodyDevice(file)
        file.setParent(multi_part)
        multi_part.append(file_part)

        reply = self.nam.post(request, multi_part)
        reply.setProperty("endpoint", endpoint)
        reply.finished.connect(lambda: self._handle_response(reply))

        multi_part.setParent(reply)

        loop = QEventLoop()
        reply.finished.connect(loop.quit)
        loop.exec()

        file.close()

        return self.result


    def simple_post(self, url, data: dict = None) -> Union[dict, QNetworkReply]:
        """Wykonuje synchroniczny request POST do podanego URL"""
        self.result = None
        self.error_occurred = False

        def try_request(url, body):
            url = QUrl(self.base_url + url)
            request = QNetworkRequest(url)
            request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

            if self.auth_token:
                request.setRawHeader(b"Authorization", f"Bearer {self.auth_token}".encode("utf-8"))

            reply = self.nam.post(request, body)
            # reply.downloadProgress.connect( lambda recv, total: self.downloadProgress.emit(self.set_progress(recv, total)))
            reply.finished.connect(lambda: self._handle_response(reply))
            return reply

        if data:
            data = str.encode(json.dumps(data))
        else:
            data = b''

        reply = try_request(url, data)

        loop = QEventLoop()
        reply.finished.connect(loop.quit)
        loop.exec()

        return self.result

    def start_listening(self) -> None:
        """
        Rozpoczyna nasłuchiwanie zdarzeń SSE z endpointu /org/notify.
        """

        self._is_sse_listening_requested = True
        if self._sse_reply is not None:
            return

        self._connect_sse()

    def _connect_sse(self) -> None:
        """
        Wykonuje request do nasłuchiwania zdarzeń.
        """

        sse_endpoint = f"org/notify?token={self.auth_token}&mode=heartbeat"
        url = QUrl(self.base_url + sse_endpoint)
        request = QNetworkRequest(url)
        request.setRawHeader(b"Accept", b"text/event-stream")
        request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)

        reply = self.nam.get(request)
        reply.setProperty("endpoint", sse_endpoint)
        
        if self._sse_reply:
            self._sse_reply.abort()
            self._sse_reply.deleteLater()

        self._sse_reply = reply

        reply.readyRead.connect(lambda: self._handle_sse_data(reply))
        reply.errorOccurred.connect(lambda: self._handle_sse_disconnect(reply))
        reply.finished.connect(lambda: self._handle_sse_disconnect(reply))

    def _handle_sse_data(self, reply) -> None:
        """
        Przetwarza dane otrzymane z SSE
        """

        data = reply.readAll().data().decode('utf-8', errors='ignore')
        
        lines = data.split('\n')
        current_event_type = None
        current_event_data = {}

        for line in lines:
            line = line.strip()
            if not line:
                if current_event_type:
                    self.event_received.emit(current_event_type, current_event_data)
                current_event_type = None
                current_event_data = {}
                continue
            
            if line.startswith("event:"):
                current_event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                try:
                    event_data_str = line[len("data:"):].strip()
                    current_event_data = json.loads(event_data_str)
                except json.JSONDecodeError:
                    current_event_data = {"raw_data": event_data_str, "message": "Non-JSON SSE data"}
                except Exception as e:
                    current_event_data = {"raw_data": event_data_str, "error": str(e)}

    def _handle_sse_disconnect(self, reply) -> None:
        """
        Obsługuje utracenie połączenia z endpointem SSE
        """
        
        if self._sse_reply == reply and self._is_sse_listening_requested:
            self._sse_reply.deleteLater()
            self._sse_reply = None
            self._schedule_sse_reconnect()

    def _schedule_sse_reconnect(self) -> None:
        """
        Przygotowuje ponowne połączenie z endpointem SSE w przypadku utracenia połączenia
        """

        if not self._is_sse_listening_requested:
            self._sse_reconnect_delay = 1000
            return

        if self._sse_reconnect_timer.isActive():
            return

        self._sse_reconnect_timer.start(self._sse_reconnect_delay)
        
        self._sse_reconnect_delay = min(self._sse_reconnect_delay * 2, self._sse_max_reconnect_delay)

    def _reconnect_sse(self) -> None:
        """
        Nawiązuje ponowne połączenie z endpointem SSE
        """

        self._connect_sse()

        if self._sse_reply and self._sse_reply.error() == QNetworkReply.NoError:
            self._sse_reconnect_delay = 1000

    def stop_listening(self) -> None:
        """
        Zatrzymuje nasłuchiwanie zdarzeń SSE z endpointu /org/notify.
        """
        self._is_sse_listening_requested = False
        if self._sse_reconnect_timer.isActive():
            self._sse_reconnect_timer.stop()

        if self._sse_reply is not None:
            self._sse_reply.abort()
            self._sse_reply.deleteLater()
            self._sse_reply = None
            self._sse_reconnect_delay = 1000

API_CLIENT = ApiClient()

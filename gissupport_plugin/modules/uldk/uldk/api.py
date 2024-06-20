from urllib.error import HTTPError
from urllib.parse import quote

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from .api_limits import RateLimitDecorator, sleep_and_retry

from qgis.core import QgsMessageLog
from qgis.core import Qgis
from gissupport_plugin.tools.requests import NetworkHandler

class RequestException(Exception):
    pass

class URL:

    def __init__(self, base_url, **params):

        self.base_url = base_url
        self.params = {}
        for k, v in params.items():
            self.set_param(k, v)

    def set_param(self, key, value):

        if isinstance(value, (tuple, list)):
            value = [str(v) for v in value]
        else:
            value = str(value)
        self.params[key] = value

    def __str__(self):
        url = self.base_url

        if self.params:
            url += "?"
        
        for key,value in self.params.items():
            if isinstance(value, (tuple, list)):
                value = ",".join(value)
            url += "{}={}&".format(key, quote(value))

        return url

class ULDKPoint:
    
    def __init__(self, x, y, srid = 2180):
        self.x = x; self.y = y; self.srid = srid

    def __iter__(self):
        yield self.x; yield self.y; yield self.srid

    def __str__(self):
        return f"{self.x} {self.y} [{self.srid}]"

class ULDKSearch:

    proxy_url = r"https://gugik.gis.support/uldk/service.php"
    gugik_url = r"http://uldk.gugik.gov.pl/service.php"

    def __init__(self, target, results, method = ""):
        self.url = URL(self.proxy_url, obiekt=target, wynik=results)
        if method:
            self.url.set_param("request", method)

    @sleep_and_retry
    @RateLimitDecorator(calls = 5, period = 3)
    def search(self):
        url = self.url
        handler = NetworkHandler()
        
        content = handler.get(str(self.url))
        if "error" in content:
            self.url = URL(self.gugik_url, **url.params)
            content = handler.get(str(self.url))
            if "error" in content:
                raise RequestException("Brak odpowiedzi")
            
        content = content["data"]
        
        content_lines = content.split("\n")
        status = content_lines[0]

        if status != "0":
            raise RequestException(status)

        content_lines = content_lines[1:]
        if content.endswith("\n"):
            content_lines = content_lines[:-1]
        return content_lines

class ULDKSearchLogger(ULDKSearch):

    """Dekorator obiektów ULDKSearch, służący do zapisywania logu wyszukiwań"""

    message_group_name = "GIS Support - wyszukiwarka działek"

    def __init__(self, decorated: ULDKSearch):
        self._decorated = decorated

    def search(self, *args, **kwargs):
        try:
            result = self._decorated.search(*args, **kwargs)
            url = str(self._decorated.url)
            self.log_message("{} - pobrano".format(url))
            return result
        except Exception as e:
            url = str(self._decorated.url)
            message = "{} - błąd {} ({})".format(url, type(e), e)
            self.log_message(message, Qgis.Critical)
            raise e

    def log_message(self, message, level=Qgis.Info):
        QgsMessageLog.logMessage(message, self.message_group_name, level)

class ULDKSearchTeryt(ULDKSearch):
    def __init__(self, target, results):
        super().__init__(target, results)
    def search(self, teryt):
        self.url.set_param("teryt", teryt)
        return super().search()

class ULDKSearchParcel(ULDKSearch):
    def __init__(self, target, results):
        super().__init__(target, results, "GetParcelById")
    def search(self, teryt):
        self.url.set_param("id", teryt)
        return super().search()

class ULDKSearchPoint(ULDKSearch):
    def __init__(self, target, results):
        super().__init__(target, results, "GetParcelByXY")
    def search(self, uldk_point):
        x, y, srid = list(uldk_point)
        self.url.set_param("xy", (x,y,srid))
        return super().search()[0]

class ULDKSearchWorker(QObject):

    found = pyqtSignal(dict)
    not_found = pyqtSignal(str, Exception)
    finished = pyqtSignal()
    interrupted = pyqtSignal()
    def __init__(self, uldk_search, teryt_ids):
        super().__init__()  
        self.uldk_search = uldk_search
        self.teryt_ids = teryt_ids

    @pyqtSlot()
    def search(self):
        for k, v in self.teryt_ids.items():
            teryt = v.get("teryt")
            if QThread.currentThread().isInterruptionRequested():
                self.interrupted.emit()
                return
            try:
                result = self.uldk_search.search(teryt)
                self.found.emit({k: result})
            except (HTTPError, RequestException) as e:  
                self.not_found.emit(teryt, e)
        self.finished.emit()

class ULDKSearchPointWorker(QObject):

    found = pyqtSignal(str)
    not_found = pyqtSignal(ULDKPoint, Exception)
    finished = pyqtSignal()
    interrupted = pyqtSignal()
    def __init__(self, uldk_point_search, uldk_points):
        super().__init__()  
        self.uldk_search = uldk_point_search
        self.points = uldk_points

    @pyqtSlot()
    def search(self):
        for point in self.points:
            if QThread.currentThread().isInterruptionRequested():
                self.interrupted.emit()
                return
            try:
                result = self.uldk_search.search(point)
                self.found.emit(result)
            except (HTTPError, RequestException) as e:  
                self.not_found.emit(point, e)
        self.finished.emit()
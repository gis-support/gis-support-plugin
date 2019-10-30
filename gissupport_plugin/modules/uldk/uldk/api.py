from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from ..lib.ratelimit import RateLimitException, limits, sleep_and_retry
from copy import deepcopy

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

    url = r"http://uldk.gugik.gov.pl/service.php"

    def __init__(self, target, results, method = ""):
        self.url = URL(ULDKSearch.url, obiekt=target, wynik=results)
        if method:
            self.url.set_param("request", method)

    @sleep_and_retry
    @limits(calls = 5, period = 3)
    def search(self):
        url = str(self.url)
        # print(url)
        # url = "http://127.0.0.1:5000/uldk_dummy"
        try:
            with urlopen(url, timeout=50) as u:
                content = u.read()
            content = content.decode()
            content_lines = content.split("\n")
            status = content_lines[0]
            if status != "0":
                raise RequestException(status)
        except HTTPError as e:
            raise e
        except URLError:
            raise RequestException("Brak odpowiedzi")
        content_lines = content_lines[1:]
        if content.endswith("\n"):
            content_lines = content_lines[:-1]
        return content_lines

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

    found = pyqtSignal(list)
    not_found = pyqtSignal(str, Exception)
    finished = pyqtSignal()
    interrupted = pyqtSignal()
    def __init__(self, uldk_search, teryt_ids):
        super().__init__()  
        self.uldk_search = uldk_search
        self.teryt_ids = teryt_ids

    @pyqtSlot()
    def search(self):
        for teryt in self.teryt_ids:
            if QThread.currentThread().isInterruptionRequested():
                self.interrupted.emit()
                return
            try:
                result = self.uldk_search.search(teryt)
                self.found.emit(result)
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
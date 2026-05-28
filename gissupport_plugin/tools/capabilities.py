from traceback import print_exc
from owslib.wmts import WebMapTileService
from qgis.core import QgsNetworkAccessManager
from owslib.wms import WebMapService
from owslib.wfs import WebFeatureService
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.PyQt.QtCore import QUrl
from typing import Union
from urllib.parse import urlencode, parse_qs, urlsplit, urlunsplit

try:
    import defusedxml.ElementTree as et
    from defusedxml.common import EntitiesForbidden
except (ModuleNotFoundError, ImportError):
    import xml.etree.ElementTree as et # nosec B405

    class EntitiesForbidden(Exception):
        """Pusta klasa wyjątku dla zachowania kompatybilności bloku try-except, gdy brak defusedxml."""
        pass

class CapabilitiesConnectionException(Exception):
    def __init__(self, code: int, *args, **kwargs):
            self.code = code
            super().__init__(*args, **kwargs)

def get_capabilities(url: str, service_type: str) -> Union[WebMapService, WebFeatureService, WebMapTileService]:
    manager = QgsNetworkAccessManager()

    scheme, netloc, path, params, _ = urlsplit(url)
    query_params = parse_qs(params)
    query_params["service"] = [f"{service_type}"]
    query_params["request"] = ["GetCapabilities"]
    new_params = urlencode(query_params, doseq=True)

    request_url = urlunsplit((scheme, netloc, path, new_params, _))
    request = QNetworkRequest(QUrl(request_url))
    reply = manager.blockingGet(request)

    if reply.error() != QNetworkReply.NetworkError.NoError or not reply.content():
        raise CapabilitiesConnectionException(code=reply.error())

    xml_data = reply.content().data()

    try:
        xml = et.fromstring(xml_data) # nosec B314
    except EntitiesForbidden as e:
        print_exc()
        raise CapabilitiesConnectionException(code=409, message=f"Dokument XML pobrany z adresu {url} zawiera potencjalnie niebezpieczne fragmenty i został zablokowany") from e
    except et.ParseError as e:
        print_exc()
        raise CapabilitiesConnectionException(code=500, message=f"Błąd parsowania XML z adresu {url}") from e

    version = xml.attrib.get("version")

    if service_type == "WMS":
        return WebMapService(url="", version=version, xml=xml_data)

    elif service_type == "WFS":
        return WebFeatureService(url="", version=version, xml=xml_data)

    elif service_type == "WMTS":
        return WebMapTileService(url="", version=version, xml=xml_data)

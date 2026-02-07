from traceback import print_exc
from typing import Union
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from owslib.wfs import WebFeatureService
from owslib.wms import WebMapService
from owslib.wmts import WebMapTileService
from qgis.core import QgsNetworkAccessManager
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

try:
  import defusedxml.ElementTree as et
  from defusedxml.common import EntitiesForbidden
except (ModuleNotFoundError, ImportError):
  import gissupport_plugin.lib.defusedxml.ElementTree as et
  from gissupport_plugin.lib.defusedxml.common import EntitiesForbidden

class CapabilitiesConnectionException(Exception):
    def __init__(self, code: int, *args, **kwargs):
            self.code = code
            super().__init__(*args, **kwargs)

def get_capabilities(url: str, type: str) -> Union[WebMapService, WebFeatureService]:
    manager = QgsNetworkAccessManager()

    scheme, netloc, path, params, _ = urlsplit(url)
    query_params = parse_qs(params)
    query_params["service"] = [f"{type}"]
    query_params["request"] = ["GetCapabilities"]
    new_params = urlencode(query_params, doseq=True)

    request_url = urlunsplit((scheme, netloc, path, new_params, _))
    request = QNetworkRequest(QUrl(request_url))
    reply = manager.blockingGet(request)
    
    if reply.error() != QNetworkReply.NoError or not reply.content():
        raise CapabilitiesConnectionException(code=reply.error())

    content = reply.content()
    data = content.data()
    try:
        xml = et.fromstring(data)
    except EntitiesForbidden as e:
        print_exc()
        raise CapabilitiesConnectionException(code=409, message=f"Dokument XML pobrany z adresu {url} zawiera potencjalnie niebezpieczne fragmenty i został zablokowany") from e
    version =  xml.attrib.get("version")
    
    if type == "WMS":
        return WebMapService(url="", version=version, xml=data)
    elif type == "WFS":
        return WebFeatureService(url="", version=version, xml=data)
    elif type == "WMTS":
        return WebMapTileService(url="", version=version, xml=data)


from qgis.core import QgsNetworkAccessManager
from owslib.wms import WebMapService
from PyQt5.QtNetwork import QNetworkRequest
from qgis.PyQt.QtCore import QUrl
from owslib.etree import ParseError

def get_wms_capabilities(url: str, version: str="1.3.0") -> WebMapService:

    if not url.endswith("?"):
        url += "?"
    
    manager = QgsNetworkAccessManager()
    try:
        wms = get_capabilities(manager, url, version)
    except (AttributeError, ParseError):
        version = "1.1.1" if version == "1.3.0" else "1.3.0"
        wms = get_capabilities(manager, url, version)

    return wms

def get_capabilities(manager: QgsNetworkAccessManager, url: str, version: str) -> WebMapService:
    request = QNetworkRequest(QUrl(f'{url}service=WMS&request=GetCapabilities&version={version}'))
    reply = manager.blockingGet(request)
    xml = reply.content()
    return WebMapService('', xml=xml.data(), version=version)
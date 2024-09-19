
from qgis.core import QgsNetworkAccessManager
from owslib.wms import WebMapService
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.PyQt.QtCore import QUrl
from owslib.etree import ParseError


class WmsCapabilitiesConnectionException(Exception):
    def __init__(self, code: int, *args, **kwargs):
            self.code = code
            super().__init__(*args, **kwargs)


def get_wms_capabilities(url: str, version: str="1.3.0") -> WebMapService:

    if not url.endswith("?"):
        url += "?"
    
    manager = QgsNetworkAccessManager()
    try:
        wms = get_capabilities(manager, url, version)
    except (AttributeError, ParseError, WmsCapabilitiesConnectionException):
        version = "1.1.1" if version == "1.3.0" else "1.3.0"
        wms = get_capabilities(manager, url, version)

    return wms

def get_capabilities(manager: QgsNetworkAccessManager, url: str, version: str) -> WebMapService:
    request = QNetworkRequest(QUrl(f'{url}service=WMS&request=GetCapabilities&version={version}'))
    reply = manager.blockingGet(request)
    if reply.error() != QNetworkReply.NoError:
        raise WmsCapabilitiesConnectionException(code=reply.error())
    
    xml = reply.content()
    if not xml:
        raise WmsCapabilitiesConnectionException(code=-1)
    return WebMapService('', xml=xml.data(), version=version)
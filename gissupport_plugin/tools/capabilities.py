
from qgis.core import QgsNetworkAccessManager
from owslib.wms import WebMapService
from PyQt5.QtNetwork import QNetworkRequest
from qgis.PyQt.QtCore import QUrl

def get_wms_capabilities(url: str, version: str = None) -> WebMapService:

    if not url.endswith("?"):
        url += "?"
    
    if not version:
        version = "1.1.1"

    manager = QgsNetworkAccessManager()
    request = QNetworkRequest(QUrl(f'{url}service=WMS&request=GetCapabilities&version={version}'))
    reply = manager.blockingGet(request)
    xml = reply.content()
    wms = WebMapService('', xml=xml.data(), version=version)

    return wms
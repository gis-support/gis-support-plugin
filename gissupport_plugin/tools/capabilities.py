
from qgis.core import QgsNetworkAccessManager
from owslib.wms import WebMapService
from owslib.wfs import WebFeatureService
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.PyQt.QtCore import QUrl
import xml.etree.ElementTree as et
from typing import Union

class CapabilitiesConnectionException(Exception):
    def __init__(self, code: int, *args, **kwargs):
            self.code = code
            super().__init__(*args, **kwargs)


def get_capabilities(url: str, type: str) -> Union[WebMapService, WebFeatureService]:
    manager = QgsNetworkAccessManager()
    
    url = f'{url}?service={type}&request=GetCapabilities'
    request = QNetworkRequest(QUrl(url))
    reply = manager.blockingGet(request)
    
    if reply.error() != QNetworkReply.NoError or not reply.content():
        raise CapabilitiesConnectionException(code=reply.error())

    content = reply.content()
    data = content.data()
    xml = et.fromstring(data)
    version =  xml.attrib.get("version")
    
    if type == "WMS":
        return WebMapService(url="", version=version, xml=data)
    elif type == "WFS":
        return WebFeatureService(url="", version=version, xml=data)

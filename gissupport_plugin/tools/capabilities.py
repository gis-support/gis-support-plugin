from owslib.wmts import WebMapTileService
from qgis.core import QgsNetworkAccessManager
from owslib.wms import WebMapService
from owslib.wfs import WebFeatureService
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.PyQt.QtCore import QUrl
from typing import Union

import gissupport_plugin.defusedxml.ElementTree as et # Ochrona przed XXE

class CapabilitiesConnectionException(Exception):
    def __init__(self, code: int, *args, **kwargs):
            self.code = code
            super().__init__(*args, **kwargs)

ALLOWED_TAGS = {
    "WMS_Capabilities", "WFS_Capabilities", "Capabilities",
    "Service", "Capability", "Request", "GetMap", "GetFeature",
    "Format", "Layer", "Name", "Title", "Abstract"
}

def get_capabilities(url: str, type: str) -> Union[WebMapService, WebFeatureService]:
    manager = QgsNetworkAccessManager()

    if type not in ["WMS", "WMTS", "WFS"]:
        raise ValueError("Invalid type. Must be one of: WMS, WMTS, WFS")
    
    url = f'{url}?service={type}&request=GetCapabilities'
    request = QNetworkRequest(QUrl(url))
    reply = manager.blockingGet(request)
    
    if reply.error() != QNetworkReply.NoError or not reply.content():
        raise CapabilitiesConnectionException(code=reply.error())

    content = reply.content()
    data = content.data()
    xml = et.fromstring(data)
    clean_xml_tree(xml)
    version =  xml.attrib.get("version")
    
    if type == "WMS":
        return WebMapService(url="", version=version, xml=data)
    elif type == "WFS":
        return WebFeatureService(url="", version=version, xml=data)
    elif type == "WMTS":
        return WebMapTileService(url="", version=version, xml=data)

def clean_xml_tree(elem):
    for child in list(elem):
        if child.tag not in ALLOWED_TAGS:
            elem.remove(child)
        else:
            clean_xml_tree(child)

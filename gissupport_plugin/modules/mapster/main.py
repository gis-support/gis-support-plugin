from qgis.gui import QgsMapToolEmitPoint
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
from qgis.utils import iface
from gissupport_plugin.modules.base import BaseModule
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtCore import QUrl, Qt
from PyQt5.QtGui import QIcon
from gissupport_plugin.modules.mapster.mapster_dockwidget import MapsterDockwidget


class MapsterModule( BaseModule ):
    module_name = "Wyszukiwarka archiwalnych map Mapster"
    
    def __init__(self, parent):
        super().__init__(parent)
        self.dockwidget = MapsterDockwidget()
        self.point_tool = QgsMapToolEmitPoint( iface.mapCanvas() )

        action = self.parent.add_action(
            ':/plugins/gissupport_plugin/mapster/mapster.svg',
            self.module_name,
            self.dockwidget.setVisible,
            parent=iface.mainWindow(),
            checkable=True,
            add_to_topmenu=True
        )
        self.point_tool.canvasClicked.connect( self.canvasClicked )
        
        self.wgs84 = QgsCoordinateReferenceSystem( 'EPSG:4326' )

        self.dockwidget.searchButton.setIcon(QIcon(":/plugins/gissupport_plugin/mapster/mapster.svg"))
        self.dockwidget.searchButton.clicked.connect(self.setMapsterTool)
        self.dockwidget.visibilityChanged.connect(action.setChecked)
        self.dockwidget.visibilityChanged.connect(self.unset_point_tool)

        iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
        self.dockwidget.hide()

    def setMapsterTool( self, checked: bool ):

        if checked:
            iface.mapCanvas().setMapTool( self.point_tool )
        else:
            iface.mapCanvas().unsetMapTool( self.point_tool )
    
    def canvasClicked( self, point, button ):
        project = QgsProject.instance()
        transformer = QgsCoordinateTransform( project.crs(), self.wgs84, project )
        point = transformer.transform( point )
        
        url = 'http://igrek.amzp.pl/result.php?cmd=pt&lat={}&lon={}&hideempty=on'.format( point.y(), point.x() )
        
        QDesktopServices.openUrl(QUrl(url))
    
    def unset_point_tool(self, visible: bool):
        if not visible:
            iface.mapCanvas().unsetMapTool(self.point_tool)
            self.dockwidget.searchButton.setChecked(False)

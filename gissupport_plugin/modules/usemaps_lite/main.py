from gissupport_plugin.modules.base import BaseModule
from gissupport_plugin.modules.usemaps_lite.ui.dockwidget import UsemapsLiteDockwidget


class UsemapsLite(BaseModule):
    """
    Moduł Usemaps Lite (GIS.Box Lite).
    """

    # Kod i cała struktura modułu zostały przeniesione w całości z osobnego repozytorium wtyczki Usemaps Lite.

    def __init__(self, parent):
        super().__init__(parent)
        self.parent.toolbar.addSeparator()
        self.dockwidget = UsemapsLiteDockwidget()


        self.dockwidgetAction = self.parent.add_dockwidget_action(
            dockwidget = self.dockwidget,
            icon_path=":/plugins/gissupport_plugin/usemaps_lite/usemaps_lite.svg",
            text = 'Usemaps Lite'
            )

        self.dockwidget.layers.connect_layersremoved_signal(True)
    
    def unload(self):
        self.dockwidget.layers.connect_layersremoved_signal(False)


# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GISSupportPlugin
                                 A QGIS plugin
 Wtyczka GIS Support
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2019-09-03
        git sha              : $Format:%H$
        copyright            : (C) 2019 by GIS Support
        email                : kamil.kozik@gis-support.pl
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os.path

from PyQt5.QtCore import (QCoreApplication, QSettings, Qt, QTranslator, QUrl,
                          qVersion)
from PyQt5.QtGui import QDesktopServices, QIcon, QPixmap
from PyQt5.QtWidgets import QAction, QLabel, QMenu, QSizePolicy

from .key_dialog import GisSupportPluginDialog
from .resources import resources

PLUGIN_NAME = "Wtyczka GIS Support"


class GISSupportPlugin:

    def __init__(self, iface):

        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'GISSupportPlugin_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr(u'&Wtyczka GIS Support')
        self.toolbar = self.iface.addToolBar(PLUGIN_NAME)
        self.toolbar.addSeparator
        
        self.first_start = None
        self.api_key_dialog = GisSupportPluginDialog()
        
    def tr(self, message):
        return QCoreApplication.translate('GISSupportPlugin', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_topmenu=False,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
        checkable = False):

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        action.setCheckable(checkable)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)
        
        if add_to_topmenu:
            self.topMenu.addAction(action)

        self.actions.append(action)

        return action

    def initGui(self):

        self.topMenu = self.iface.mainWindow().menuBar().addMenu(u'&GIS Support')

        self._init_uldk_module()

        self.topMenu.addSeparator()
        self.topMenu.setObjectName('gisSupportMenu')
        self.add_action(
            icon_path=None,
            text="Klucz GIS Support",
            add_to_menu=False,
            add_to_topmenu=True,
            callback=self.show_api_key_dialog,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False
        )
        self.add_action(
            icon_path=':/plugins/gissupport_plugin/gissupport_small.jpg',
            text="O wtyczce",
            add_to_menu=False,
            add_to_topmenu=True,
            callback=self.open_about,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False
        )

        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.toolbar.clear()
        self.toolbar.deleteLater()
        self.topMenu.clear()
        self.topMenu.deleteLater()

    def _init_uldk_module(self):
        from .modules.uldk.main import Main
        from .modules.uldk.modules.map_point_search.main import MapPointSearch
        main = Main(self.iface)
        dockwidget = main.dockwidget
        self.uldk_module = main
        self.iface.addDockWidget(Qt.RightDockWidgetArea, main.dockwidget)
        dockwidget_icon_path = ":/plugins/gissupport_plugin/uldk/search.png"

        self.uldk_toolbar_action = self.add_action(
            dockwidget_icon_path,
            main.module_name,
            lambda state: dockwidget.setHidden(not state),
            checkable = True,
            parent = self.iface.mainWindow(),
            add_to_topmenu=True 
        )

        dockwidget.visibilityChanged.connect(self.uldk_toolbar_action.setChecked)

        intersect_icon_path = ":/plugins/gissupport_plugin/uldk/intersect.png"
        self.identify_toolbar_action = self.add_action(
            intersect_icon_path,
            text = "Identifykacja ULDK",
            callback = lambda toggle: self.uldk_module.identifyAction.trigger(),
            parent = self.iface.mainWindow(),
            checkable = True,
            add_to_topmenu=True
        )
        self.uldk_module.identifyAction.toggled.connect(
            lambda changed: self.identify_toolbar_action.setChecked(changed)
        )

    def show_api_key_dialog(self):
        self.api_key_dialog.show()

    def open_about(self):
        QDesktopServices.openUrl(QUrl('https://gis-support.pl/nowa-wtyczka-gis-support-wyszukiwarka-dzialek-ewidencyjnych-uldk-gugik-beta'))

# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/home/kamil/Dokumenty/gissupport/projekty/wtyczki/uldk/wyszukiwarka-gugik-uldk/wyszukiwarka-gugik-uldk/plugin_dockwidget_base.ui'
#
# Created by: PyQt5 UI code generator 5.10.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_DockWidget(object):
    def setupUi(self, DockWidget):
        DockWidget.setObjectName("DockWidget")
        DockWidget.resize(370, 808)
        self.dockWidgetContents = QtWidgets.QWidget()
        self.dockWidgetContents.setObjectName("dockWidgetContents")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.dockWidgetContents)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.label_uldk_info = QtWidgets.QLabel(self.dockWidgetContents)
        self.label_uldk_info.setTextFormat(QtCore.Qt.RichText)
        self.label_uldk_info.setOpenExternalLinks(True)
        self.label_uldk_info.setObjectName("label_uldk_info")
        self.verticalLayout_2.addWidget(self.label_uldk_info)
        self.tabs = QtWidgets.QTabWidget(self.dockWidgetContents)
        self.tabs.setObjectName("tabs")
        self.tab_search = QtWidgets.QWidget()
        self.tab_search.setObjectName("tab_search")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.tab_search)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout_3.addLayout(self.verticalLayout)
        self.tabs.addTab(self.tab_search, "")
        self.tab_import_csv = QtWidgets.QWidget()
        self.tab_import_csv.setObjectName("tab_import_csv")
        self.verticalLayout_7 = QtWidgets.QVBoxLayout(self.tab_import_csv)
        self.verticalLayout_7.setObjectName("verticalLayout_7")
        self.tab_import_csv_layout = QtWidgets.QVBoxLayout()
        self.tab_import_csv_layout.setObjectName("tab_import_csv_layout")
        self.verticalLayout_7.addLayout(self.tab_import_csv_layout)
        self.tabs.addTab(self.tab_import_csv, "")
        self.verticalLayout_2.addWidget(self.tabs)
        spacerItem = QtWidgets.QSpacerItem(20, 15, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
        self.verticalLayout_2.addItem(spacerItem)
        spacerItem1 = QtWidgets.QSpacerItem(20, 5, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.verticalLayout_2.addItem(spacerItem1)
        spacerItem2 = QtWidgets.QSpacerItem(20, 15, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.verticalLayout_2.addItem(spacerItem2)
        self.line = QtWidgets.QFrame(self.dockWidgetContents)
        self.line.setFrameShape(QtWidgets.QFrame.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line.setObjectName("line")
        self.verticalLayout_2.addWidget(self.line)
        spacerItem3 = QtWidgets.QSpacerItem(20, 15, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.verticalLayout_2.addItem(spacerItem3)
        self.button_wms = QtWidgets.QPushButton(self.dockWidgetContents)
        self.button_wms.setObjectName("button_wms")
        self.verticalLayout_2.addWidget(self.button_wms)
        self.verticalLayout_4 = QtWidgets.QVBoxLayout()
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.verticalLayout_2.addLayout(self.verticalLayout_4)
        spacerItem4 = QtWidgets.QSpacerItem(17, 79, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout_2.addItem(spacerItem4)
        spacerItem5 = QtWidgets.QSpacerItem(20, 15, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
        self.verticalLayout_2.addItem(spacerItem5)
        DockWidget.setWidget(self.dockWidgetContents)

        self.retranslateUi(DockWidget)
        self.tabs.setCurrentIndex(1)
        QtCore.QMetaObject.connectSlotsByName(DockWidget)

    def retranslateUi(self, DockWidget):
        _translate = QtCore.QCoreApplication.translate
        DockWidget.setWindowTitle(_translate("DockWidget", "Wyszukiwarka działek ewidencyjnych (GUGiK ULDK)"))
        self.label_uldk_info.setText(_translate("DockWidget", "<html><head/><body><p>Więcej informacji na  <a href=\"https://gis-support.pl/wyszukiwarka-dzialek-ewidencyjnych-uldk-gugik/\"><span style=\" text-decoration: underline; color:#0000ff;\">stronie wtyczki</span></a></p></body></html>"))
        self.tabs.setTabText(self.tabs.indexOf(self.tab_search), _translate("DockWidget", "Wyszukiwanie"))
        self.tabs.setTabText(self.tabs.indexOf(self.tab_import_csv), _translate("DockWidget", "Import z CSV"))
        self.button_wms.setText(_translate("DockWidget", "Dodaj WMS do mapy"))


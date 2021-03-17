import os

from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'prg_dockwidget.ui'))


class PRGDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super(PRGDockWidget, self).__init__(parent)
        self.setupUi(self)
        self.setWindowTitle("PRG - granice administracyjne")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

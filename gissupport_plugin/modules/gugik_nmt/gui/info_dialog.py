# -*- coding: utf-8 -*-
import os

from qgis.PyQt import QtGui, uic
from qgis.PyQt.QtWidgets import QDialog 

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'info_dialog.ui'))

class InfoDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(InfoDialog, self).__init__(parent=parent)
        self.setupUi(self)
from qgis.PyQt.QtCore import QAbstractTableModel, Qt, QModelIndex, QSortFilterProxyModel

class ServicesTableModel(QAbstractTableModel):
    
    def __init__(self, parent=None):
        super(ServicesTableModel, self).__init__(parent)
        self.items = []

    def rowCount(self, parent=QModelIndex()):
        return len(self.items)
    
    def columnCount(self, parent=QModelIndex()):
        return 4

    def insertRows(self, position, rows, parent=QModelIndex()):
        self.beginInsertRows(parent, position, position + len(rows) - 1)
        for i, item in enumerate(rows):
            self.items.insert(position + i, item)
        self.endInsertRows()
        return True
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:    
            if section == 0:
                return 'ID'
            elif section == 1:
                return 'Źródło'
            elif section == 2:
                return 'Nazwa'
            elif section == 3:
                return 'URL'

    def data(self, index, role):
        if not index.isValid():
            return
        item = self.items[index.row()]
        if role == Qt.DisplayRole:
            if index.column() == 0:
                return item['id']
            elif index.column() == 1:
                return item['source']
            elif index.column() == 2:
                return item['name']
            elif index.column() == 3:
                return item['url']
        elif role == Qt.UserRole:
            return item
        return     

class ServicesProxyModel(QSortFilterProxyModel):

    def filterAcceptsRow(self, source_row, source_parent):
        pattern = self.filterRegExp().pattern()
        if self.filterRegExp().isEmpty():
            return True
        index = self.sourceModel().index(source_row, 0, source_parent)
        value = self.sourceModel().data(index, role=Qt.UserRole)
        for key in ['Źródło', 'Nazwa', 'Opis']:
            if value[key].casefold().__contains__(pattern.casefold()):
                return True
        return False
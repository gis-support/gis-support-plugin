from qgis.PyQt.QtCore import QAbstractTableModel, Qt, QModelIndex, QSortFilterProxyModel

class ServicesTableModel(QAbstractTableModel):
    
    def __init__(self, parent=None):
        super(ServicesTableModel, self).__init__(parent)
        self.items = []

    def rowCount(self, parent=QModelIndex()):
        return len(self.items)
    
    def columnCount(self, parent=QModelIndex()):
        return 5

    def insertRows(self, position, rows, parent=QModelIndex()):
        self.beginInsertRows(parent, position, position + len(rows) - 1)
        for i, item in enumerate(rows):
            self.items.insert(position + i, item)
        self.endInsertRows()
        return True

    def removeRows(self, row=None, count=None, parent=QModelIndex()):
        if count == None:
            count = len(self.items)
        if row == None:
            row = 0
        self.beginRemoveRows(parent, row, row+count-1)
        for i in reversed(list(range(row, row+count))):
            del self.items[i]
        self.endRemoveRows()
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:    
            if section == 0:
                return 'ID'
            elif section == 1:
                return 'Źródło'
            elif section == 2:
                return 'Typ'
            elif section == 3:
                return 'Nazwa'
            elif section == 4:
                return 'Opis'

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
                return item['type']
            elif index.column() == 3:
                return '{}, {}'.format(item['name'], item['url'])
            elif index.column() == 4:
                return item['description']
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
        for key in ['source', 'type', 'name', 'description']:
            if value[key].casefold().__contains__(pattern.casefold()):
                return True
        return False
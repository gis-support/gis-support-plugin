from qgis.PyQt.QtCore import Qt

from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR


class UserMapper:
    """
    Klasa łącząca UUID członków organizacji z ich adresami email.
    """
    
    def __init__(self):
        
        self.users_tableview_model = None

    def set_users_model(self, users_tableview_model):
        
        self.users_tableview_model = users_tableview_model
    
    def get_user_email(self, user_uuid: str):
        """
        Zwraca adres email członka na podstawie jego UUID.
        """
        for user_row in range(self.users_tableview_model.rowCount()):
            item = self.users_tableview_model.item(user_row, 0)
            if item and item.data(Qt.UserRole) == user_uuid:
                return item.text()
        return f"({TRANSLATOR.translate_ui('removed')})"

    def get_user_uuid(self, user_email: str):
        """
        Zwraca UUID członka na podstawie jego adresu email.
        """
    
        for user_row in range(self.users_tableview_model.rowCount()):
            item = self.users_tableview_model.item(user_row, 0)
            if item and item.text() == user_email:
                uuid = item.data(Qt.UserRole)
                return uuid
        return f"({TRANSLATOR.translate_ui('removed')})"

USER_MAPPER = UserMapper()

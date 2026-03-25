from typing import Dict, Any

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtGui import QIcon, QStandardItem
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QMessageBox, QHeaderView

from gissupport_plugin.tools.usemaps_lite.base_logic_class import BaseLogicClass
from gissupport_plugin.tools.usemaps_lite.event_handler import Event
from gissupport_plugin.tools.usemaps_lite.user_mapper import USER_MAPPER
from gissupport_plugin.tools.usemaps_lite.metadata import ORGANIZATION_METADATA
from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR
from gissupport_plugin.modules.usemaps_lite.ui.invite_user import InviteUserDialog


class Organization(BaseLogicClass):
    """
    Klasa obsługująca logikę związaną z organizacją
    1. zapraszanie członków
    2. usuwanie członków
    """
    def __init__(self, dockwidget: QtWidgets.QDockWidget):

        super().__init__(dockwidget)

        self.invite_user_dialog = InviteUserDialog()
        
        self.event_handler.register_event_handler(Event.INVITED_USER, self.handle_invited_user_event)
        self.event_handler.register_event_handler(Event.VERIFIED_USER, self.handle_verified_user_event)
        self.event_handler.register_event_handler(Event.DELETED_USER, self.handle_deleted_user_event)
        self.event_handler.register_event_handler(Event.NEW_COMMENT, self.handle_new_comment_event)
        self.event_handler.register_event_handler(Event.ONLINE_USER, self.handle_online_user_event)
        self.event_handler.register_event_handler(Event.OFFLINE_USER, self.handle_offline_user_event)

        self.dockwidget.users_tableview.setColumnWidth(0, 200)
        self.dockwidget.users_tableview.setColumnWidth(1, 120)
        self.dockwidget.users_tableview.setColumnWidth(2, 50)
        self.dockwidget.users_tableview.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.dockwidget.users_tableview.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.dockwidget.users_tableview.selectionModel().selectionChanged.connect(self.on_users_tableview_selection_changed)

        self.dockwidget.remove_user_button.clicked.connect(self.remove_selected_user)
        self.dockwidget.remove_user_button.setEnabled(False)

        self.invite_user_dialog.invite_user_button.clicked.connect(self.invite_user)

        self.dockwidget.invite_user_button.clicked.connect(self.invite_user_dialog.show)
        
        self.dockwidget.add_comment_button.clicked.connect(self.post_comment)
        self.dockwidget.comment_lineedit.returnPressed.connect(self.post_comment)
        self.dockwidget.comment_lineedit.textChanged.connect(self.check_comment)

    def check_comment(self, comment: str) -> None:
        """
        Aktywuje przycisk dodania komentarza po sprawdzeniu czy faktycznie wpisano tekst.
        """

        enable_button = True
        if len(comment) == 0:
            enable_button = False

        self.dockwidget.add_comment_button.setEnabled(enable_button)
        
    def post_comment(self) -> None:
        """
        Wykonuje request dodania komentarza
        """

        comment = self.dockwidget.comment_lineedit.text()
        
        self.api.post(
            "org/comments",
            {"comment": comment},
            callback=self.handle_comment_response
        )
    
    def handle_comment_response(self, response: Dict[str, Any]) -> None:
        """
        Obsługuje odpowiedź po próbie dodania komentarza.
        """

        if (error_msg := response.get("error")) is not None:
            self.show_error_message(f"{TRANSLATOR.translate_error('comment')}: {error_msg}")

        else:
            self.dockwidget.comment_lineedit.clear()


    def invite_user(self) -> None:
        """
        Wykonuje request zaproszenia nowego członka do organizacji
        """

        user_email = self.invite_user_dialog.email_line.text()

        self.api.post(
            "org/invite",
            {"email": user_email},
            callback=self.handle_user_invite_response
        )

    def handle_user_invite_response(self, response: Dict[str, Any]) -> None:
        """
        Obsługuje odpowiedź po próbie zaproszenia nowego członka
        """

        if (error_msg := response.get("error")) is not None:

            if error_msg.get('server_message') == 'user already exists':
                self.show_error_message(TRANSLATOR.translate_error("invite user exists"))

            else:
                self.show_error_message(f"{TRANSLATOR.translate_error('invite')}: {error_msg.get('server_message')}")

        else:
            self.show_success_message(TRANSLATOR.translate_info("invite send"))
            self.invite_user_dialog.hide()


    def remove_selected_user(self) -> None:
        """
        Wykonuje request usunięcia wybranego członka organizacji
        """

        reply = QMessageBox.question(
            self.dockwidget,
            TRANSLATOR.translate_ui("remove user label"),
            TRANSLATOR.translate_ui("remove user question"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:

            selected_index = self.dockwidget.users_tableview.selectedIndexes()
            user_email = selected_index[0].data()

            self.api.delete(
                "org/users",
                {"email": user_email},
                callback=self.handle_delete_user_response
            )
        
    def handle_delete_user_response(self, response: Dict[str, Any]) -> None:
        """
        Obsługuje odpowiedź po próbie usunięcia członka organizacji
        """

        if (error_msg := response.get("error")) is not None:
            self.show_error_message(f"{TRANSLATOR.translate_error('remove user')}: {error_msg}")

    def on_users_tableview_selection_changed(self) -> None:
        """
        Prosty check, aktywuje przycisk usuwania userów tylko jak jest jakiś user zaznaczony
        """

        selected_indexes = self.dockwidget.users_tableview.selectedIndexes()
        has_selection = bool(selected_indexes)
        self.dockwidget.remove_user_button.setEnabled(has_selection)

    def handle_invited_user_event(self, event_data: Dict[str, Any]) -> None:
        """
        Obsługuje przychodzące zdarzenie zaproszenia nowego członka do organizacji.
        """

        data = event_data.get("data")

        email = data.get("email")
        user_uuid = data.get("uuid")
        verified = TRANSLATOR.translate_info("yes") if data.get("verified") else TRANSLATOR.translate_info("no")

        email_item = QStandardItem(email)
        email_item.setData(user_uuid, Qt.ItemDataRole.UserRole)

        icon = QIcon(":images/themes/default/repositoryDisabled.svg")
        icon_item = QStandardItem()
        icon_item.setIcon(icon)

        row = [
            email_item,
            QStandardItem(verified),
            icon_item
        ]

        self.dockwidget.users_tableview_model.appendRow(row)
        self.toggle_invite_user_button()

    def handle_verified_user_event(self, event_data: Dict[str, Any]) -> None:
        """
        Obsługuje przychodzące zdarzenie weryfikacji nowego członka organizacji.
        """        

        data = event_data.get("data")
        email = data.get("email")

        for user_row in range(self.dockwidget.users_tableview_model.rowCount()):
            item = self.dockwidget.users_tableview_model.item(user_row, 0)
            if item and item.text() == email:
                verified_item = QStandardItem("Tak")
                icon = QIcon(":images/themes/default/repositoryConnected.svg")
                icon_item = QStandardItem()
                icon_item.setIcon(icon)
                self.dockwidget.users_tableview_model.setItem(user_row, 1, verified_item)
                self.dockwidget.users_tableview_model.setItem(user_row, 2, icon_item)

    def handle_deleted_user_event(self, event_data: Dict[str, Any]) -> None:
        """
        Obsługuje przychodzące zdarzenie usunięcia członka organizacji.
        """

        data = event_data.get("data")
        user_uuid = data.get("uuid")
        email = data.get("email")

        row_to_remove = -1

        for row_index in range(self.dockwidget.users_tableview_model.rowCount()):
            item_email = self.dockwidget.users_tableview_model.item(row_index, 0)
            if item_email and item_email.data(Qt.ItemDataRole.UserRole) == user_uuid:
                row_to_remove = row_index
                break

        if row_to_remove != -1:
            self.dockwidget.users_tableview_model.removeRow(row_to_remove)

        if email == ORGANIZATION_METADATA.get_logged_user_email():
            self.show_info_message(TRANSLATOR.translate_info('removed from org'))
            self.dockwidget.auth.logout()

        self.toggle_invite_user_button()

    def handle_new_comment_event(self, event_data: Dict[str, Any]) -> None:
        """
        Obsługuje przychodzące zdarzenie nowego komentarza.
        """

        user_uuid = event_data.get("user")
        user_email = USER_MAPPER.get_user_email(user_uuid)
        self.show_info_message(f"{user_email} {TRANSLATOR.translate_info('added new comment')}")

    def toggle_invite_user_button(self):
        """
        Włącza/wyłącza przycisk zapraszania współpracowników, w zaleznosci od osiągnięcia
        limitu współpracowników w organizacji
        """
        
        num_of_users_limit = ORGANIZATION_METADATA.get_num_of_users_limit()
        num_of_users_added = self.dockwidget.users_tableview_model.rowCount()
        
        self.dockwidget.invite_user_button.setEnabled(num_of_users_added < num_of_users_limit)

    def handle_online_user_event(self, event_data: Dict[str, Any]) -> None:
        """
        Obsługuje przychodzące zdarzenie zalogowania współpracownika
        """

        data = event_data.get("data")
        online_user_uuid = data.get("uuid")
        online_user_email = USER_MAPPER.get_user_email(online_user_uuid)

        for user_row in range(self.dockwidget.users_tableview_model.rowCount()):
            item = self.dockwidget.users_tableview_model.item(user_row, 0)
            if item and item.text() == online_user_email:
                icon = QIcon(":images/themes/default/repositoryConnected.svg")
                icon_item = QStandardItem()
                icon_item.setIcon(icon)
                self.dockwidget.users_tableview_model.setItem(user_row, 2, icon_item)

                
        self.show_info_message(f"{online_user_email} {TRANSLATOR.translate_info('is online')}")


    def handle_offline_user_event(self, event_data: Dict[str, Any]) -> None:
        """
        Obsługuje przychodzące zdarzenie zalogowania współpracownika
        """

        data = event_data.get("data")
        online_user_uuid = data.get("uuid")
        online_user_email = USER_MAPPER.get_user_email(online_user_uuid)

        for user_row in range(self.dockwidget.users_tableview_model.rowCount()):
            item = self.dockwidget.users_tableview_model.item(user_row, 0)
            if item and item.text() == online_user_email:
                icon = QIcon(":images/themes/default/repositoryDisabled.svg")
                icon_item = QStandardItem()
                icon_item.setIcon(icon)
                self.dockwidget.users_tableview_model.setItem(user_row, 2, icon_item)

        self.show_info_message(f"{online_user_email} {TRANSLATOR.translate_info('is offline')}")


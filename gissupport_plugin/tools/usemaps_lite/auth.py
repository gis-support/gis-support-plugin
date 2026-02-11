from typing import Dict, Any

from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon
from PyQt5.Qt import QStandardItem
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsSettings

from gissupport_plugin.tools.usemaps_lite.base_logic_class import BaseLogicClass
from gissupport_plugin.tools.usemaps_lite.event_handler import Event
from gissupport_plugin.tools.usemaps_lite.metadata import ORGANIZATION_METADATA
from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR
from gissupport_plugin.modules.usemaps_lite.ui.login import LoginDialog
from gissupport_plugin.modules.usemaps_lite.ui.register import RegisterDialog
from gissupport_plugin.modules.usemaps_lite.ui.verify_org import VerifyOrgDialog
from gissupport_plugin.modules.usemaps_lite.ui.forgot_password import ForgotPasswordDialog



class Auth(BaseLogicClass):

    """
    Klasa obsługująca logikę związaną z autoryzacją
    1. logowanie
    2. rejestracja
    3. weryfikacja usera
    """

    def __init__(self, dockwidget: QtWidgets.QDockWidget):
        super().__init__(dockwidget)

        self.registered_user_uuid = None

        self.login_dialog = LoginDialog()
        self.register_dialog = RegisterDialog()
        self.verify_org_dialog = VerifyOrgDialog()
        self.forgot_password_dialog = ForgotPasswordDialog()

        self.dockwidget.login_button.clicked.connect(self.login_dialog.show)
        self.dockwidget.register_button.clicked.connect(self.register_dialog.show)

        self.login_dialog.login_button.clicked.connect(self.login)
        self.login_dialog.forgot_pwd_button.clicked.connect(self.show_forgot_password_dialog)
        self.register_dialog.reg_register_button.clicked.connect(self.register)

        self.verify_org_dialog.verify_button.clicked.connect(self.verify_org)
        self.verify_org_dialog.cancel_button.clicked.connect(self.register_dialog.show) #Anulowanie weryfikacji, przywraca okno rejestracji

        self.forgot_password_dialog.reset_button.clicked.connect(self.reset_password)
        self.forgot_password_dialog.cancel_button.clicked.connect(self.login_dialog.show) #Anulowanie resetu hasla, przywraca okno loginu

        self.dockwidget.logout_button.clicked.connect(self.logout)

        self.dockwidget.events_listview.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)


    def login(self) -> None:
        """
        Wykonuje request logowania do Usemaps Lite.
        """
        self.username = self.login_dialog.log_email_line.text()
        self.pwd = self.login_dialog.log_pwd_line.text()

        self.api.post(
            "auth/login",
            {"email": self.username, "password": self.pwd},
            callback=self.handle_login_response
        )

    def handle_login_response(self, response: Dict[str, Any]) -> None:
        """
        Obsługuje odpowiedź po próbie zalogowania do Usemaps Lite.
        """

        if (error_msg := response.get("error")) is not None:

            server_message = error_msg.get("server_message")
            if server_message == 'invalid credentials':
                self.show_error_message(TRANSLATOR.translate_error('invalid credentials'))

            else:
                self.show_error_message(f"{TRANSLATOR.translate_error('login')}: {error_msg.get('server_message')}")
            return

        settings = QgsSettings()

        settings.setValue("usemaps_lite/login", self.username)
        settings.setValue("usemaps_lite/pwd", self.pwd)

        data = response.get("data")
        self.api.auth_token = data.get('token')

        ORGANIZATION_METADATA.set_logged_user_email(self.username)
        self.api.get("org/metadata", callback=self.handle_metadata_response)
        self.show_success_message(TRANSLATOR.translate_info("logged in"))
        self.api.start_listening()
        self.login_dialog.hide()

    def handle_metadata_response(self, response: Dict[str, Any]) -> None:
        """
        Obsługuje pobrane metadane organizacji
        """

        if (error_msg := response.get("error")) is not None:
            self.show_error_message(f"{TRANSLATOR.translate_error('metadata')}: {error_msg.get('server_message')}")

        else:
            self.dockwidget.events_tab.setEnabled(True)
            self.dockwidget.layers_tab.setEnabled(True)
            self.dockwidget.users_tab.setEnabled(True)

            self.dockwidget.login_button.setVisible(False)
            self.dockwidget.register_button.setVisible(False)

            self.dockwidget.logout_button.setVisible(True)

            data = response.get("data")
            user_info = data.get('user')
            org_members_info = data.get('users')
            limits_info = data.get('limits')

            num_of_users_limit = limits_info.get('limitUsers')

            if len(org_members_info) == num_of_users_limit:
                self.dockwidget.invite_user_button.setEnabled(False)

            ORGANIZATION_METADATA.set_logged_user_email(user_info.get('email'))
            ORGANIZATION_METADATA.set_num_of_users_limit(num_of_users_limit)
            ORGANIZATION_METADATA.set_mb_limit(limits_info.get('limitMb'))

            self.dockwidget.user_info_label.setText(f"{user_info.get('email')} {TRANSLATOR.translate_ui('user_info_label')}: {user_info.get('organizationName')}")
            self.dockwidget.limit_progressbar.setValue(user_info.get('limitUsed'))

            num_of_users = 0

            # wypełnianie tabeli z członkami organizacji
            for org_member in org_members_info:
                num_of_users += 1
                email = org_member.get('email')
                user_uuid = org_member.get('uuid')
                verified = TRANSLATOR.translate_info("yes") if org_member.get('verified') else TRANSLATOR.translate_info("no")
                is_online = org_member.get('online')

                email_item = QStandardItem(email)
                email_item.setData(user_uuid, Qt.UserRole)


                online_icon_path = ":images/themes/default/repositoryDisabled.svg"
                if is_online:
                    online_icon_path = ":images/themes/default/repositoryConnected.svg"

                online_icon = QIcon(online_icon_path)
                online_icon_item = QStandardItem()
                online_icon_item.setIcon(online_icon)

                row = [
                    email_item,
                    QStandardItem(verified),
                    online_icon_item
                ]

                self.dockwidget.users_tableview_model.appendRow(row)

            self.dockwidget.org_members_label.setText(f"{TRANSLATOR.translate_ui('coworkers')} ({num_of_users}/{ORGANIZATION_METADATA.get_num_of_users_limit()})")

            # wypełnianie listy z warstwami organizacji
            layers = data.get("layers", [])

            for layer in layers:
                layer_name = layer.get("name")
                layer_uuid = layer.get("uuid")
                layer_type = layer.get("type")

                layer_item = QStandardItem(layer_name)
                layer_item.setData(layer_uuid, Qt.UserRole)
                layer_item.setData(layer_type, Qt.UserRole + 1)

                row = [
                    layer_item
                ]

                self.dockwidget.layers_model.appendRow(row)

            # wypełnianie listy z eventami organizacji
            events = data.get("events")

            for event_item in events:
                event_name_str = event_item.get("name")
                event_type = Event(event_name_str)
                formatted_message, aligment, full_date_str = self.event_handler.format_event_message(event_item)
                if formatted_message:
                    self.event_handler.add_event_to_list_model(formatted_message, event_type, aligment, full_date_str, add_to_top=True)

    def register(self):
        """
        Wykonuje request rejestracji w Usemaps Lite.
        """

        self.username = self.register_dialog.reg_email_line.text()
        orgname = self.register_dialog.reg_orgname_line.text()
        self.pwd = self.register_dialog.reg_pwd_line.text()
        pwd_again = self.register_dialog.reg_pwd_again_line.text()


        self.api.post(
            "auth/register",
            {
                "email": self.username,
                "name": orgname,
                "password": self.pwd,
                "passwordRepeat": pwd_again
            },
            callback=self.handle_register_response
        )

    def handle_register_response(self, response: Dict[str, Any]) -> None:
        """
        Obsługuje odpowiedź po próbie rejestracji w Usemaps Lite.
        """
        if (error_msg := response.get("error")) is not None:

            server_message = error_msg.get('server_message')

            if server_message is not None:

                if server_message == "user already exists":
                    self.show_error_message(TRANSLATOR.translate_error("register user exists"))

                if 'validation errors' in server_message:

                    if "'Email'" in server_message:
                        self.show_error_message(TRANSLATOR.translate_error("email validation"))

                    elif "'Password" in server_message:

                        if 'failed validation: max' in server_message:
                            self.show_error_message(TRANSLATOR.translate_error("password too long"))

                        elif 'failed validation: min' in server_message:
                            self.show_error_message(TRANSLATOR.translate_error("password too short"))

                        elif 'failed validation: eqfield' in server_message:
                            self.show_error_message(TRANSLATOR.translate_error("password not equal"))

                        else:
                            self.show_error_message(TRANSLATOR.translate_error("password validation"))

                else:
                    self.show_error_message(f"{TRANSLATOR.translate_error('register')}: {error_msg.get('server_message')}")

            else:
                self.show_error_message(f"{TRANSLATOR.translate_error('register')}: {error_msg}")

        else:
            data = response.get("data")
            self.registered_user_uuid = data.get('uuid')
            self.register_dialog.hide() #Ukrycie okna rejestracji
            self.verify_org_dialog.show()

    def verify_org(self) -> None:
        """
        Wykonuje request weryfikacji rejestracji w Usemaps Lite.
        """

        verify_code = self.verify_org_dialog.code_line.text()

        self.api.post(
            "auth/users/verify",
            {"code": int(verify_code), "uuid": self.registered_user_uuid},
            callback=self.handle_verify_response
            )

    def handle_verify_response(self, response: Dict[str, Any]) -> None:
        """
        Obsługuje odpowiedź po próbie weryfikacji rejestracji w Usemaps Lite.
        """
        if response.get("error")is not None:
            self.show_error_message(TRANSLATOR.translate_error("verification"))

        else:
            self.verify_org_dialog.hide()
            self.register_dialog.hide()

            self.api.post(
                "auth/login",
                {"email": self.username, "password": self.pwd},
                callback=self.handle_login_response
            )

    def logout(self):
        """
        Wylogowuje aktualnie zalogowanego usera Usemaps Lite.
        """

        self.dockwidget.events_tab.setEnabled(False)
        self.dockwidget.layers_tab.setEnabled(False)
        self.dockwidget.users_tab.setEnabled(False)

        self.dockwidget.user_info_label.setText(TRANSLATOR.translate_ui("user"))
        self.dockwidget.limit_progressbar.setValue(0)
        self.dockwidget.org_members_label.setText(TRANSLATOR.translate_ui("coworkers"))

        self.api.auth_token = None
        self.api.stop_listening()
        self.registered_user_uuid = None

        self.dockwidget.login_button.setVisible(True)
        self.dockwidget.register_button.setVisible(True)
        self.dockwidget.logout_button.setVisible(False)

        self.dockwidget.remove_user_button.setEnabled(False)
        self.dockwidget.remove_layer_button.setEnabled(False)

        self.dockwidget.users_tableview_model.removeRows(0, self.dockwidget.users_tableview_model.rowCount())
        self.dockwidget.layers_model.removeRows(0, self.dockwidget.layers_model.rowCount())
        self.dockwidget.events_listview_model.removeRows(0, self.dockwidget.events_listview_model.rowCount())
        self.dockwidget.comment_lineedit.clear()

    def show_forgot_password_dialog(self) -> None:

        typed_email = self.login_dialog.log_email_line.text()
        self.forgot_password_dialog.reset_email_line.setText(typed_email)
        self.login_dialog.hide() #Ukrycie okna logowania, aby nie zasłaniało
        self.forgot_password_dialog.show()

    def reset_password(self):

        email = self.forgot_password_dialog.reset_email_line.text()

        self.api.post(
            "auth/reset",
            {"email": email},
            callback=self.handle_reset_password_response
        )

    def handle_reset_password_response(self, response: Dict[str, Any]) -> None:

        if (error_msg := response.get("error")) is not None:

            self.show_error_message(TRANSLATOR.translate_error("reset password"))

        else:

            self.forgot_password_dialog.hide()
            self.login_dialog.hide()

            self.show_success_message(TRANSLATOR.translate_info("reset email send"))

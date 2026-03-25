from datetime import datetime
from enum import Enum
from typing import Tuple

from qgis.PyQt.QtCore import QObject, Qt
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QColor

from gissupport_plugin.tools.usemaps_lite.requests import API_CLIENT
from gissupport_plugin.tools.usemaps_lite.user_mapper import USER_MAPPER
from gissupport_plugin.tools.usemaps_lite.metadata import ORGANIZATION_METADATA
from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR

class Event(Enum):
    STATUS = 'status'
    INVITED_USER = 'invited_user'
    VERIFIED_USER = 'verified_user'
    DELETED_USER = 'deleted_user'
    DELETED_LAYER = 'deleted_layer'
    UPLOADED_LAYER = 'uploaded_layer'
    EDITED_LAYER = 'edited_layer'
    CHANGED_LIMIT = 'changed_limit'
    NEW_COMMENT = 'new_comment'
    ONLINE_USER = 'online_user'
    OFFLINE_USER = 'offline_user'


class EventHandler(QObject):
    """
    Klasa obsługująca komunikację z Usemaps Lite przy pomocy SSE
    """

    def __init__(self):
        super().__init__()
        self.api = API_CLIENT
        self._event_handlers = {}

        self.events_listview_model = None

        self.api.event_received.connect(self.handle_event)

    def set_events_listview_model(self, model: QStandardItemModel) -> None:
        """
        Przypisuje do klasy model listy z aktywnościami.
        """

        self.events_listview_model = model

    def register_event_handler(self, event_type: str, handler_function) -> None:
        """
        Rejestruje metodę dla danego typu zdarzenia.
        """

        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []

        self._event_handlers[event_type].append(handler_function)

    def handle_event(self, event_type_str: str, event_data: dict) -> None:
        """
        Główna metoda dystrybucji zdarzeń.
        Odbiera wszystkie zdarzenia i przekazuje je do zarejestrowanych handlerów,
        a także dodaje je do event_list_model.
        """

        event_type = Event(event_type_str)

        if event_type == Event.STATUS or event_data.get("message") == "heartbeat":
            # nie obsługujemy zdarzeń związanych z utrzymaniem połączenia
            return

        formatted_message, alignment, full_date_str = self.format_event_message(event_data)

        if formatted_message:
            self.add_event_to_list_model(formatted_message, event_type, alignment, full_date_str, add_to_top=False)

        try:
            event_type_enum = Event(event_type_str)
        except ValueError:
            return

        handlers = self._event_handlers.get(event_type_enum, [])
        if not handlers:
            return

        for handler in handlers:
            handler(event_data)

    def format_event_message(self, event_data: dict) -> Tuple[str, Qt.AlignmentFlag]:
        """
        Formatuje odebraną aktywność do formy wiadomości, wyświetlanej w liście z ostatnimi aktywnościami
        """

        event_name = event_data.get("name")
        data = event_data.get("data", {})
        user_uuid = event_data.get("user")
        timestamp = event_data.get("timestamp")

        date_str, full_date_str = "", ""

        if timestamp:
            dt_object = datetime.fromtimestamp(timestamp)
            full_date_str = dt_object.strftime("%Y-%m-%d %H:%M:%S")
            date_str = dt_object.strftime("%H:%M")

        user_email = USER_MAPPER.get_user_email(user_uuid)
        logged_user_email = ORGANIZATION_METADATA.get_logged_user_email()

        message = f"{user_email} [{date_str}]\n"
        alignment = Qt.AlignmentFlag.AlignCenter # Domyślne wyrównanie (dla paska na środku)

        try:
            event_type = Event(event_name)
        except ValueError:
            message += f" {event_name}"
            return message, alignment, full_date_str

        if event_type == Event.NEW_COMMENT:
            comment_text = data.get("comment", "")
            if user_email == logged_user_email:
                alignment = Qt.AlignmentFlag.AlignRight
            else:
                alignment = Qt.AlignmentFlag.AlignLeft
            message += comment_text

        elif event_type == Event.INVITED_USER:
            invited_email = data.get("email", "N/A")
            message += f"{TRANSLATOR.translate_info('invited user event')} {invited_email}"

        elif event_type == Event.VERIFIED_USER:
            message += TRANSLATOR.translate_info("verified user event")

        elif event_type == Event.DELETED_USER:
            deleted_email = data.get("email", "N/A")
            message += f"{TRANSLATOR.translate_info('deleted user event')} {deleted_email}"

        elif event_type == Event.UPLOADED_LAYER:
            layer_name = data.get("name", "N/A")
            message += f"{TRANSLATOR.translate_info('uploaded layer event')} {layer_name}"

        elif event_type == Event.EDITED_LAYER:
            layer_name = data.get("name", "N/A")
            updated = data.get("updated", 0)
            inserted = data.get("inserted", 0)
            deleted = data.get("deleted", 0)
            message += f"{TRANSLATOR.translate_info('edited layer event')} {layer_name} ({TRANSLATOR.translate_info('added')}: {inserted}, {TRANSLATOR.translate_info('edited')}: {updated}, {TRANSLATOR.translate_info('removed')}: {deleted})"

        elif event_type == Event.DELETED_LAYER:
            layer_name = data.get("name", "N/A")
            message += f"{TRANSLATOR.translate_info('deleted layer event')} {layer_name}"

        else:
            return "", alignment, full_date_str

        return message, alignment, full_date_str

    def add_event_to_list_model(self, message_text: str, event_type_enum: Event = None, alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter, full_date_str: str = "", add_to_top = False) -> None:
        """
        Dodaje sformatowaną wiadomość o zdarzeniu do QStandardItemModel, z opcjonalnym kolorem tła.
        """

        item = QStandardItem(message_text)
        background_color = self._get_event_background_color(event_type_enum)

        item.setData(event_type_enum, Qt.ItemDataRole.UserRole + 1) 
        item.setData(alignment, Qt.ItemDataRole.UserRole + 2)
        item.setToolTip(full_date_str)

        if background_color:
            item.setBackground(background_color)

        if add_to_top:
            self.events_listview_model.insertRow(0, item)
        else:
            self.events_listview_model.appendRow(item)

    def _get_event_background_color(self, event_type: Event) -> QColor:
        """
        Zwraca QColor dla danego typu zdarzenia.
        Pozostałość po pierwotnej implementacji web -> qgis.
        Teraz tylko komentarze mają kolorowe dymki, reszta nie ma tła.
        """

        color_map = {
            #Event.UPLOADED_LAYER: QColor("#e7d2fb"),
            #Event.DELETED_LAYER: QColor("#FFCCCC"),
            #Event.DELETED_USER: QColor("#FFCCCC"),
            Event.NEW_COMMENT: QColor("#E6F5FF"),
            #Event.INVITED_USER: QColor("#E6F5FF"),
            #Event.VERIFIED_USER: QColor("#E6F5FF"),
            #Event.EDITED_LAYER: QColor("#F0FFF0"),
        }

        return color_map.get(event_type, QColor("#FFFFFF"))

EVENT_HANDLER = EventHandler()

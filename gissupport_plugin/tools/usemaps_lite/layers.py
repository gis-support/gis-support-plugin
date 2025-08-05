import json
from typing import Dict, List, Any
import os 

from PyQt5.QtWidgets import QMessageBox
from PyQt5 import QtWidgets
from PyQt5.QtGui import QStandardItem
from qgis.PyQt.QtCore import Qt, QMetaType,  QDate, QDateTime, QTime, pyqtSignal
from PyQt5.QtCore import QObject
from qgis.utils import iface
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsFeature,
    QgsJsonUtils,
    QgsField,
    QgsFields,
    NULL,
    QgsFeatureRequest,
    QgsEditorWidgetSetup,
    QgsTask,
    QgsApplication
)

from gissupport_plugin.tools.usemaps_lite.base_logic_class import BaseLogicClass
from gissupport_plugin.tools.usemaps_lite.event_handler import Event
from gissupport_plugin.tools.usemaps_lite.gpkg_handler import GpkgHandler
from gissupport_plugin.tools.usemaps_lite.user_mapper import USER_MAPPER
from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR
from gissupport_plugin.tools.usemaps_lite.metadata import ORGANIZATION_METADATA
from gissupport_plugin.modules.usemaps_lite.ui.import_layer import ImportLayerDialog


class Layers(BaseLogicClass, QObject):
    """
    Klasa obsługująca logikę związaną z warstwami
    1. wgrywanie plików GPKG do organizacji
    2. wczytywanie warstw organizacji do QGIS
    3. edycja warstw
    4. usuwanie warstw
    """

    def __init__(self, dockwidget: QtWidgets.QDockWidget):

        QObject.__init__(self, dockwidget)
        BaseLogicClass.__init__(self, dockwidget)

        self.dockwidget.layers_listview.selectionModel().selectionChanged.connect(self.on_layers_listview_selection_changed)
        self.dockwidget.layers_listview.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.dockwidget.layers_listview.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.dockwidget.layers_listview.doubleClicked.connect(self.get_selected_layer)

        self.dockwidget.remove_layer_button.clicked.connect(self.remove_selected_layer)
        self.dockwidget.remove_layer_button.setEnabled(False)

        self.import_layer_dialog = ImportLayerDialog()

        self.import_layer_dialog.drop_file_dropzone.file_dropped.connect(self.handle_gpkg_file_response)
        self.import_layer_dialog.select_file_button.clicked.connect(self.browse_gpkg_file)
        self.import_layer_dialog.add_button.clicked.connect(self.handle_selected_gpkg_layer_from_dialog)

        self.dockwidget.import_layer_button.clicked.connect(self.import_layer_dialog.show)

        self.event_handler.register_event_handler(Event.DELETED_LAYER, self.handle_deleted_layer_event)
        self.event_handler.register_event_handler(Event.UPLOADED_LAYER, self.handle_uploaded_layer_event)
        self.event_handler.register_event_handler(Event.EDITED_LAYER, self.handle_edited_layer_event)
        self.event_handler.register_event_handler(Event.CHANGED_LIMIT, self.handle_changed_limit_event)

        self.gpkg_handler = GpkgHandler()

    def get_selected_layer(self, index) -> None:
        """
        Wykonuje request pobrania geojsona wybranej warstwy.
        """

        selected_layer = index.sibling(index.row(), 0)
        selected_layer_uuid = selected_layer.data(Qt.UserRole)

        self.selected_layer_name = selected_layer.data()
        self.selected_layer_type = selected_layer.data(Qt.UserRole + 1)
        self.selected_layer_uuid = selected_layer_uuid

        self.show_info_message(f"{TRANSLATOR.translate_info('load layer start')}: {self.selected_layer_name}")

        layer = QgsVectorLayer(f"{self.selected_layer_type.capitalize()}?crs=EPSG:4326", self.selected_layer_name, "memory")
        layer.setCustomProperty("skipMemoryLayersCheck", 1)

        self.task = self.LoadLayerToQgisTask(self.selected_layer_name, self.selected_layer_uuid,
                                            layer, self)
        self.task.download_finished.connect(lambda _: self.on_load_layer_finished(layer))

        manager = QgsApplication.taskManager()
        manager.addTask(self.task)

    class LoadLayerToQgisTask(QgsTask):

        download_finished = pyqtSignal(bool)

        def __init__(self, layer_name: str, layer_uuid: str, layer, parent):
            description = f"{TRANSLATOR.translate_info('layer loading')}: {layer_name}"
            self.layer_uuid = layer_uuid
            self.layer = layer
            super().__init__(description, QgsTask.CanCancel)
            self.parent = parent

        def run(self):

            response = self.parent.api.simple_get(f"org/layers/{self.layer_uuid}/geojson")

            if (error_msg := response.get("error")) is not None:

                self.show_error_message(f"{TRANSLATOR.translate_error('load layer')}: {error_msg}")
                return

            self.data = response.get("data")
            provider = self.layer.dataProvider()

            fields = QgsFields()

            example_props = self.data["features"][0].get("properties", {})

            fields.append(QgsField("_id", QMetaType.Int))

            for key, value in example_props.items():
                value_type = type(value)
                if value_type == int:
                    fields.append(QgsField(key, QMetaType.Int))
                elif value_type == float:
                    fields.append(QgsField(key, QMetaType.Double))
                else:
                    fields.append(QgsField(key, QMetaType.QString))

            provider.addAttributes(fields)
            self.layer.updateFields()
            self.layer.setEditorWidgetSetup(self.layer.fields().indexOf('_id'), QgsEditorWidgetSetup('Hidden', {}))

            for feat_data in self.data["features"]:
                feat = QgsFeature()
                feat.setFields(fields)

                attributes = []
                for field in fields:
                    if field.name() == "_id":
                        attributes.append(feat_data.get("id"))
                    else:
                        attributes.append(feat_data["properties"].get(field.name()))
                feat.setAttributes(attributes)

                geometry = QgsJsonUtils.geometryFromGeoJson(json.dumps(feat_data.get("geometry")))
                feat.setGeometry(geometry)

                provider.addFeatures([feat])

            self.layer.updateExtents()
            self.layer.beforeCommitChanges.connect(self.parent.update_layer)

            project = QgsProject.instance()
            custom_variables = project.customVariables()
            stored_mappings = custom_variables.get("usemaps_lite/id") or ''
            mappings = json.loads(stored_mappings) if stored_mappings else {}    

            layer_qgis_id = self.layer.id()

            if layer_qgis_id not in mappings:
                mappings[layer_qgis_id] = self.layer_uuid
                custom_variables["usemaps_lite/id"] = json.dumps(mappings)
                project.setCustomVariables(custom_variables)

            project.addMapLayer(self.layer)
            self.download_finished.emit(True)

            return True

        def finished(self, result: bool):
            pass

    def on_load_layer_finished(self, layer):
        """
        Usuwa ikonkę warstwy tymczasowej i wyświetla komunikat wczytania warstwy
        """
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        indicators = iface.layerTreeView().indicators(node)
        if indicators:
            iface.layerTreeView().removeIndicator(node, indicators[0])            

        self.show_success_message(f"{TRANSLATOR.translate_info('load layer success')}: {self.selected_layer_name}")

    def browse_gpkg_file(self) -> None:
        """
        Wyświetla dialog do wskazania pliku GPKG do importu.
        """

        # w momencie przeglądania plików, zdejmujemy flagi zeby dialog importu nie zakrywal file dialogu
        self.import_layer_dialog.setWindowFlags(self.import_layer_dialog.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.import_layer_dialog.show()

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.dockwidget,
            TRANSLATOR.translate_ui("select_file"),
            "",
            TRANSLATOR.translate_ui("file_filter")
        )

        self.import_layer_dialog.setWindowFlags(self.import_layer_dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        self.import_layer_dialog.show()        

        if file_path:
            self.handle_gpkg_file_response(file_path)


    def handle_gpkg_file_response(self, file_path) -> None:
        """
        Weryfikuje wybrany plik GPKG.
        """

        self.current_gpkg_file_path = file_path

        layer_infos = self.gpkg_handler.get_layer_info(self.current_gpkg_file_path)

        if len(layer_infos) == 1:
            # TYLKO JEDNA WARSTWA: przekaż oryginalny plik GPKG
            self.upload_layer_to_api(file_path, is_temp_file=False)
            return
        else:
            # WIELE WARSTW: wyświetl combobox z wyborem warstw
            for info in layer_infos:
                self.import_layer_dialog.layer_combobox.addItem(info.get('icon'), info.get('name'))

            self.import_layer_dialog.layer_combobox.setVisible(True)
            self.import_layer_dialog.layer_label.setVisible(True)
            self.import_layer_dialog.add_button.setVisible(True)

    def handle_selected_gpkg_layer_from_dialog(self) -> None:
        """
        Obsługuje wgranie wybranej warstwy z GPKG.
        """

        selected_layer_name = self.import_layer_dialog.layer_combobox.currentText()

        uri = f"{self.current_gpkg_file_path}|layername={selected_layer_name}"

        temp_gpkg_path = self.gpkg_handler.extract_layer_to_temp_gpkg(uri, selected_layer_name)

        self.upload_layer_to_api(temp_gpkg_path, is_temp_file=True)

    def upload_layer_to_api(self, file_path_to_upload: str, is_temp_file: bool) -> None:
        """
        Ogólna metoda do wysyłania pliku
        (oryginalnego GPKG lub tymczasowo wyodrębnionej warstwy)
        do Usemaps Lite.
        """

        self.import_layer_dialog.hide()
        self.show_info_message(TRANSLATOR.translate_info('import layer start'))


        self.task = self.UploadLayerTask(file_path_to_upload, is_temp_file,
                                            self)
        self.task.upload_finished.connect(self.on_upload_layer_finished)

        manager = QgsApplication.taskManager()
        manager.addTask(self.task)

    def on_upload_layer_finished(self):
        """
        Wyświetla komunikat wgrania warstwy
        """
        self.show_success_message(f"{TRANSLATOR.translate_info('import layer success')}")

    class UploadLayerTask(QgsTask):

        upload_finished = pyqtSignal(bool)

        def __init__(self, file_path_to_upload: str, is_temp_file: str, parent):
            description = f"{TRANSLATOR.translate_info('import layer start')}"
            self.file_path_to_upload = file_path_to_upload
            self.is_temp_file = is_temp_file
            super().__init__(description, QgsTask.CanCancel)
            self.parent = parent

        def run(self):

            response = self.parent.api.simple_post_file("org/upload", self.file_path_to_upload)

            if (error_msg := response.get("error")) is not None:

                if (nested_error := error_msg.get("error")) is not None:
                    if nested_error == 'Nie można zapisać' or 'Entity Too Large' in nested_error:
                        # nginx
                        self.show_error_message(TRANSLATOR.translate_error("gpkg too large", params={"mb_limit": ORGANIZATION_METADATA.get_mb_limit()}))
                        return

                if (server_msg := error_msg.get("server_message")) is not None:
                    if 'ogrinfo' in server_msg:
                        self.show_error_message(TRANSLATOR.translate_error('ogr error'))

                    elif server_msg == "limit exceeded":
                        self.show_error_message(TRANSLATOR.translate_error('limit exceeded'))

                    else:
                        self.show_error_message(f"{TRANSLATOR.translate_error('import layer')}: {server_msg}")

                    return

                else:
                    self.show_error_message(f"{TRANSLATOR.translate_error('import layer')}: {error_msg}")
                    return

            else:
                self.show_success_message(TRANSLATOR.translate_info('import layer success'))

            # Sprzątanie: usuń plik TYLKO jeśli był to plik tymczasowy
            if self.is_temp_file and os.path.exists(self.file_path_to_upload):
                os.remove(self.file_path_to_upload)
            self.upload_finished.emit(True)
            return True

        def finished(self, result: bool):
            pass

    def remove_selected_layer(self):
        """
        Wykonuje request usunięcia z organizacji wybranej warstwy.
        """

        selected_index = self.dockwidget.layers_listview.selectedIndexes()
        layer_name = selected_index[0].data()
        
        reply = QMessageBox.question(
            self.dockwidget,
            TRANSLATOR.translate_ui("remove layer label"),
            f"{TRANSLATOR.translate_ui('remove layer question 1')} {layer_name}{TRANSLATOR.translate_ui('remove layer question 2')}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:

            uuid = selected_index[0].data(Qt.UserRole)

            self.api.delete(
                "org/layers",
                {"uuid": uuid},
                callback=self.handle_delete_layer_response
            )

    def handle_delete_layer_response(self, response: Dict[str, Any]) -> None:
        """
        Obsługuje odpowiedź po próbie usunięcia warstwy.
        """

        if (error_msg := response.get("error")) is not None:
            self.show_error_message(f"{TRANSLATOR.translate_error('remove layer')}: {error_msg}")


    def on_layers_listview_selection_changed(self) -> None:
        """
        Prosta kontrolka włączająca guzik usuwania warstw
        w momencie zaznaczenie warstwy na liście.
        """

        selected_indexes = self.dockwidget.layers_listview.selectedIndexes()
        has_selection = bool(selected_indexes)
        self.dockwidget.remove_layer_button.setEnabled(has_selection)

    def update_layer(self) -> None:
        """
        Wykonuje request aktualizacji edytowanej warstwy.
        """

        layer = self.sender()
        edit_buffer = layer.editBuffer()

        project = QgsProject.instance()
        custom_variables = project.customVariables()
        stored_mappings = custom_variables.get("usemaps_lite/id") or ''
        mappings = json.loads(stored_mappings) if stored_mappings else {}    

        layer_uuid = mappings.get(layer.id())

        payload = {"uuid": layer_uuid}

        to_add = self.get_added_features(edit_buffer)
        if to_add:
            payload['inserted'] = to_add

        to_update = self.get_updated_features(layer, edit_buffer)
        if to_update:
            payload['updated'] = to_update

        to_delete = self.get_deleted_features(layer, edit_buffer)
        if to_delete:
            payload['deleted'] = to_delete

        self.api.post(
            "org/layers",
            payload,
            callback=self.handle_update_layer_response
        )

    def handle_update_layer_response(self, response: Dict[str, Any]) -> None:
        """
        Obsługuje odpowiedź po próbie zapisu zmian w warstwie.
        """

        if (error_msg := response.get("error")) is not None:

            if (server_msg := error_msg.get("server_message")) is not None:
                self.show_error_message(f"{TRANSLATOR.translate_error('edit layer')}: {server_msg}")
            else:
                self.show_error_message(f"{TRANSLATOR.translate_error('edit layer')}: {error_msg}")
            return        

    def get_added_features(self, edit_buffer) -> List[Dict[str, Any]]:
        """ 
        Zwraca listę z dodanymi obiektami do warstwy
        """

        added_features = edit_buffer.addedFeatures().values()
        features_data = []

        for feature in added_features:
            attributes = feature.attributes()
            names = feature.fields().names()

            # Pomijamy _id w properties
            properties = {
                names[i]: self.sanetize_data_type(attributes[i]) if attributes[i] != NULL else None
                for i in range(len(names)) if names[i] != "_id"
            }

            f = {
                "type": "Feature",
                "geometry": json.loads(feature.geometry().asJson()) if feature.hasGeometry() else None,
                "properties": properties
            }

            features_data.append(f)

        return features_data


    def get_deleted_features(self, layer, edit_buffer) -> List[int]:
        """
        Zwraca listę z ID usuniętych obiektów z warstwy
        """
        return [f["_id"] for f in layer.dataProvider().getFeatures( QgsFeatureRequest().setFilterFids( edit_buffer.deletedFeatureIds() ))]

    def get_updated_features(self, layer, edit_buffer) -> List[Dict[str, Any]]:
        """
        Zwraca listę z edytowanymi obiektami w warstwie.
        """

        changed_attributes = edit_buffer.changedAttributeValues()
        changed_geometries = edit_buffer.changedGeometries()

        fids = list(set(changed_attributes.keys()) | set(changed_geometries.keys()))
        features = []

        for feature in layer.getFeatures(QgsFeatureRequest().setFilterFids(fids)):
            attributes = feature.attributes()
            names = feature.fields().names()

            # Ustawiamy ID z pola _id
            feature_id = feature.attribute("_id")

            # Pomijamy _id w properties
            properties = {
                names[i]: self.sanetize_data_type(attributes[i]) if attributes[i] != NULL else None
                for i in range(len(names)) if names[i] != "_id"
            }

            f = {
                "type": "Feature",
                "id": feature_id,
                "geometry": json.loads(feature.geometry().asJson()) if feature.hasGeometry() else None,
                "properties": properties
            }

            features.append(f)

        return features

    
    def sanetize_data_type(self, value: Any) -> str:
        """
        Formatuje wybrane typy danych do string.
        """

        if isinstance(value, QDateTime):
            value = value.toString('yyyy-MM-dd hh:mm:ss')
        elif isinstance(value, QDate):
            value = value.toString('yyyy-MM-dd')
        elif isinstance(value, QTime):
            value = value.toString('hh:mm:ss')
        return value

    def connect_layersremoved_signal(self, connect: bool):
        """
        Podłącza/rozłącza sygnał aktualizujący zmienną z mapowaniem id załadowanych warstw.
        """
        if connect:
            QgsProject.instance().layersRemoved.connect(self.remove_layer_from_projects_mappings)
        else:
            QgsProject.instance().layersRemoved.disconnect(self.remove_layer_from_projects_mappings)

    def remove_layer_from_projects_mappings(self, layer_qgis_ids: List[str]):
        project = QgsProject.instance()
        custom_variables = project.customVariables()
        stored_mappings = custom_variables.get("usemaps_lite/id") or ''
        mappings = json.loads(stored_mappings) if stored_mappings else {}    

        for layer_qgis_id in layer_qgis_ids:
            if layer_qgis_id in mappings:
                del mappings[layer_qgis_id]

        custom_variables["usemaps_lite/id"] = json.dumps(mappings)
        project.setCustomVariables(custom_variables)

    def handle_deleted_layer_event(self, event_data: Dict[str, Any]) -> None:
        """
        Obsługuje przychodzące zdarzenie usunięcia warstwy z organizacji.
        """

        data = event_data.get("data")
        layer_uuid = data.get("uuid")
        layer_name = data.get("name")
        
        row_to_remove = -1
        
        for layer_row in range(self.dockwidget.layers_model.rowCount()):
            item = self.dockwidget.layers_model.item(layer_row, 0)
            if item and item.data(Qt.UserRole) == layer_uuid:
                row_to_remove = layer_row
                break
        
        if row_to_remove != -1:
            self.dockwidget.layers_model.removeRow(row_to_remove)

        user_email = USER_MAPPER.get_user_email(event_data.get("user"))

        self.show_info_message(f"{user_email} {TRANSLATOR.translate_info('removed layer')} {layer_name}")

    def handle_uploaded_layer_event(self, event_data: Dict[str, Any]) -> None:
        """
        Obsługuje przychodzące zdarzenie wgrania warstwy do organizacji.
        """

        data = event_data.get("data")
        
        layer_name = data.get("name")
        layer_uuid = data.get("uuid")
        layer_type = data.get("type")

        layer_item = QStandardItem(layer_name)
        layer_item.setData(layer_uuid, Qt.UserRole)
        layer_item.setData(layer_type, Qt.UserRole + 1)

        row = [
            layer_item
        ]

        self.dockwidget.layers_model.appendRow(row)

        user_email = USER_MAPPER.get_user_email(event_data.get("user"))

        self.show_info_message(f"{user_email} {TRANSLATOR.translate_info('added layer')} {layer_name}")

    def handle_edited_layer_event(self, event_data: Dict[str, Any]) -> None:
        """
        Obsługuje przychodzące zdarzenie edycji warstwy z organizacji.
        """

        data = event_data.get("data")
        layer_name = data.get("name")
        layer_uuid = data.get("uuid")

        user_email = USER_MAPPER.get_user_email(event_data.get("user"))

        self.refresh_layer(layer_uuid, user_email)
        
        self.show_info_message(f"{user_email} {TRANSLATOR.translate_info('edited layer')} {layer_name}")

    def refresh_layer(self, layer_uuid: str, user_email: str) -> None:
        """
        Pobiera najnowszą wersję warstwy
        """

        project = QgsProject.instance()
        custom_variables = project.customVariables()
        stored_mappings = custom_variables.get("usemaps_lite/id") or ''
        mappings = json.loads(stored_mappings) if stored_mappings else {}    

        layer_qgis_id = next((layer_qgis_id for layer_qgis_id, mapped_layer_uuid in mappings.items() if mapped_layer_uuid == layer_uuid), None)

        if not layer_qgis_id:
            # zaktualizowana warstwa nie jest wczytana do qgis, skip
            return

        self.refreshed_layer = project.mapLayer(layer_qgis_id)
        
        if self.refreshed_layer.isEditable() and user_email != ORGANIZATION_METADATA.get_logged_user_email():
            # zaktualizowana warstwa jest aktualnie przez nas edytowana i to nie były nasze zmiany: nie nadpisujemy jej
            return

        self.api.get(
            f"org/layers/{layer_uuid}/geojson",
            callback=self.handle_refresh_layer_response
        )

    def handle_refresh_layer_response(self, response: Dict[str, Any]) -> None:

        provider = self.refreshed_layer.dataProvider()

        # odpinamy sygnał zeby nie robic zbednych strzalow do zapisu zmian
        self.refreshed_layer.beforeCommitChanges.disconnect(self.update_layer)

        self.refreshed_layer.startEditing()

        all_ids = [f.id() for f in self.refreshed_layer.getFeatures()]
        provider.deleteFeatures(all_ids)

        fields = self.refreshed_layer.fields()
        new_features = []

        data = response.get("data")

        for feat_data in data["features"]:
            feat = QgsFeature()
            feat.setFields(fields)

            attributes = [
                feat_data.get("id", "") if field.name() == "_id"
                else feat_data["properties"].get(field.name())
                for field in fields
            ]

            feat.setAttributes(attributes)

            geometry = QgsJsonUtils.geometryFromGeoJson(json.dumps(feat_data.get("geometry")))
            feat.setGeometry(geometry)

            new_features.append(feat)

        provider.addFeatures(new_features)
        self.refreshed_layer.commitChanges()
        self.refreshed_layer.updateExtents()

        # przypinamy znowu
        self.refreshed_layer.beforeCommitChanges.connect(self.update_layer)

    def handle_changed_limit_event(self, event_data: Dict[str, Any]) -> None:
        """
        Obsługuje przychodzące zdarzenie zmiany wykorzystanego limitu danych w organizacji.
        """
        
        data = event_data.get("data")
        value = data.get("limitUsed")
        
        self.dockwidget.limit_progressbar.setValue(value)

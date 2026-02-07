import json
from pathlib import Path
from typing import Any, Dict, List

from qgis.core import (
    NULL,
    Qgis,
    QgsApplication,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsJsonUtils,
    QgsProject,
    QgsTask,
    QgsVectorLayer,
)
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import (
    QDate,
    QDateTime,
    QMetaType,
    QObject,
    Qt,
    QTime,
    QVariant,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QStandardItem
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.utils import iface

from gissupport_plugin.modules.usemaps_lite.ui.import_layer import ImportLayerDialog
from gissupport_plugin.tools.usemaps_lite.base_logic_class import BaseLogicClass
from gissupport_plugin.tools.usemaps_lite.event_handler import Event
from gissupport_plugin.tools.usemaps_lite.gpkg_handler import GpkgHandler
from gissupport_plugin.tools.usemaps_lite.metadata import ORGANIZATION_METADATA
from gissupport_plugin.tools.usemaps_lite.translations import TRANSLATOR
from gissupport_plugin.tools.usemaps_lite.user_mapper import USER_MAPPER


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

        self.import_layer_dialog.add_button.clicked.connect(self.handle_import_from_project)

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
        self.task.download_finished.connect(lambda was_downloaded: self.on_load_layer_finished(was_downloaded, layer),
                                            Qt.QueuedConnection)

        manager = QgsApplication.taskManager()
        manager.addTask(self.task)

    def handle_import_from_project(self) -> None:
        """
        Pobiera wybraną warstwę z projektu QGIS, eksportuje do GPKG i wysyła.
        """
        layer = self.import_layer_dialog.layer_combobox.currentLayer()

        if not layer:
            return

        # Zapis warstwy do tymczasowego GPKG
        temp_path = self.gpkg_handler.save_layer_to_temp_gpkg(
            layer,
            layer.id() in json.loads(QgsProject.instance().customVariables().get("usemaps_lite/id", "{}"))
        )

        if temp_path:
            self.upload_layer_to_api(Path(temp_path))

    class LoadLayerToQgisTask(QgsTask):

        download_finished = pyqtSignal(bool)

        def __init__(self, layer_name: str, layer_uuid: str, layer, parent):
            description = f"{TRANSLATOR.translate_info('layer loading')}: {layer_name}"
            self.layer_uuid = layer_uuid
            self.layer = layer
            self.parent = parent
            self.error_msg = None
            super().__init__(description, QgsTask.CanCancel)

        def run(self):
            try:
                response = self.parent.api.simple_get(f"org/layers/{self.layer_uuid}/geojson")
                if (error := response.get("error")) is not None:
                    self.error_msg = f"{TRANSLATOR.translate_error('load layer')}: {error}"
                    return False

                data = response.get("data")
                if not data:
                    return False

                features = data.get("features", [])
                provider = self.layer.dataProvider()
                fields = QgsFields()

                # Bezpieczne pobieranie przykładu pól
                example_props = {}
                if features:
                    example_props = features[0].get("properties") or {}
                else:
                    empty_res = self.parent.api.simple_get(f"org/layers/{self.layer_uuid}/empty")
                    if empty_res and not empty_res.get("error"):
                        example_props = empty_res.get("data") or {}

                # Definiowanie pól
                if Qgis.QGIS_VERSION_INT >= 34000:
                    fields.append(QgsField("_id", QMetaType.Int))
                    for key, value in example_props.items():
                        if isinstance(value, int):
                            fields.append(QgsField(key, QMetaType.Int))
                        elif isinstance(value, float):
                            fields.append(QgsField(key, QMetaType.Double))
                        else:
                            fields.append(QgsField(key, QMetaType.QString))
                else:
                    fields.append(QgsField("_id", QVariant.Int))
                    for key, value in example_props.items():
                        if isinstance(value, int):
                            fields.append(QgsField(key, QVariant.Int))
                        elif isinstance(value, float):
                            fields.append(QgsField(key, QVariant.Double))
                        else:
                            fields.append(QgsField(key, QVariant.String))

                provider.addAttributes(fields)
                self.layer.updateFields()

                for feat_data in features:
                    feat = QgsFeature(fields)
                    props = feat_data.get("properties") or {} # Zabezpieczenie przed None

                    attrs = []
                    for field in fields:
                        if field.name() == "_id":
                            attrs.append(feat_data.get("id"))
                        else:
                            attrs.append(props.get(field.name()))

                    feat.setAttributes(attrs)
                    geom_str = json.dumps(feat_data.get("geometry"))

                    if Qgis.QGIS_VERSION_INT >= 33600:
                        geometry = QgsJsonUtils.geometryFromGeoJson(geom_str)
                    else:
                        tmp_feats = QgsJsonUtils.stringToFeatureList(f'{{"type":"Feature","geometry":{geom_str}}}', QgsFields())
                        geometry = tmp_feats[0].geometry() if tmp_feats else QgsGeometry()

                    feat.setGeometry(geometry)
                    provider.addFeatures([feat])

                self.layer.updateExtents()
                return True
            except Exception as e:
                self.error_msg = str(e)
                return False

        def finished(self, result: bool):
            if not result:
                if self.error_msg:
                    self.parent.show_error_message(self.error_msg)
                self.download_finished.emit(False)
                return

            QgsProject.instance().addMapLayer(self.layer)
            self.layer.beforeCommitChanges.connect(self.parent.update_layer)
            project = QgsProject.instance()
            project_config = project.customVariables()

            mappings = json.loads(project_config.get("usemaps_lite/id", "{}"))
            mappings[self.layer.id()] = self.layer_uuid

            project_config["usemaps_lite/id"] = json.dumps(mappings)
            project.setCustomVariables(project_config)

            self.download_finished.emit(True)

    def on_load_layer_finished(self, was_downloaded, layer):
        """
        Usuwa ikonkę warstwy tymczasowej i wyświetla komunikat wczytania warstwy
        """

        if not was_downloaded:
            self.show_error_message(f"{TRANSLATOR.translate_error('cannot load empty gpkg')}")
            return

        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        indicators = iface.layerTreeView().indicators(node)
        if indicators:
            iface.layerTreeView().removeIndicator(node, indicators[0])

        self.show_success_message(f"{TRANSLATOR.translate_info('load layer success')}: {self.selected_layer_name}")

    def upload_layer_to_api(self, file_path_to_upload: Path) -> None:
        """
        Ogólna metoda do wysyłania pliku
        (oryginalnego GPKG lub tymczasowo wyodrębnionej warstwy)
        do Usemaps Lite.
        """

        self.import_layer_dialog.hide()
        self.show_info_message(TRANSLATOR.translate_info('import layer start'))


        self.task = self.UploadLayerTask(file_path_to_upload,
                                            self)
        self.task.upload_finished.connect(self.on_upload_layer_finished, Qt.QueuedConnection)

        manager = QgsApplication.taskManager()
        manager.addTask(self.task)

    def on_upload_layer_finished(self):
        """
        Wyświetla komunikat wgrania warstwy
        """
        self.show_success_message(f"{TRANSLATOR.translate_info('import layer success')}")

    class UploadLayerTask(QgsTask):

        upload_finished = pyqtSignal(bool)

        def __init__(self, file_path_to_upload: Path, parent):
            description = f"{TRANSLATOR.translate_info('import layer start')}"
            self.file_path_to_upload = file_path_to_upload
            super().__init__(description, QgsTask.CanCancel)
            self.parent = parent
            self.error_msg = None

        def run(self):
            try:
                response = self.parent.api.simple_post_file("org/upload", str(self.file_path_to_upload))

                if (error_msg := response.get("error")) is not None:
                    # Zamiast wyświetlać błąd, zapisujemy go i kończymy (return False)
                    if (nested_error := error_msg.get("error")) is not None:
                        if nested_error == 'Nie można zapisać' or 'Entity Too Large' in nested_error:
                            self.error_msg = TRANSLATOR.translate_error("gpkg too large", params={"mb_limit": ORGANIZATION_METADATA.get_mb_limit()})
                            return False

                    if (server_msg := error_msg.get("server_message")) is not None:
                        if 'ogrinfo' in server_msg:
                            self.error_msg = TRANSLATOR.translate_error('ogr error')
                        elif server_msg == "limit exceeded":
                            self.error_msg = TRANSLATOR.translate_error('limit exceeded')
                        else:
                            self.error_msg = f"{TRANSLATOR.translate_error('import layer')}: {server_msg}"
                        return False
                    else:
                        self.error_msg = f"{TRANSLATOR.translate_error('import layer')}: {error_msg}"
                        return False

                self.upload_finished.emit(True)
                return True
            except Exception as e:
                self.error_msg = str(e)
                return False

        def finished(self, result: bool):
            """Wywoływane po zakończeniu run(). Bezpieczne usuwanie plików"""
            if self.file_path_to_upload.exists():
                try:
                    self.file_path_to_upload.unlink()
                except PermissionError:
                    pass
                
            if not result and self.error_msg:
                self.parent.show_error_message(self.error_msg)

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

            geojson_str = json.dumps(feat_data.get("geometry"))

            if Qgis.QGIS_VERSION_INT >= 33600:
                # Dostępna metoda od QGIS 3.36
                geometry = QgsJsonUtils.geometryFromGeoJson(geojson_str)
            else:
                feats = QgsJsonUtils.stringToFeatureList(
                    f'{{"type":"Feature","geometry":{geojson_str}}}', QgsFields())
                geometry = feats[0].geometry() if feats else QgsGeometry()

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
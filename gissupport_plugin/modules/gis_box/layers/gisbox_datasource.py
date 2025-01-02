import time
import json
from osgeo import ogr, gdal
gdal.UseExceptions()

from typing import Iterable, Any, Dict, List
from qgis.core import (QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsEditFormConfig, QgsEditorWidgetSetup,
                       QgsAttributeEditorContainer, QgsAttributeEditorField, QgsMapLayer, NULL, QgsFieldConstraints,
                       QgsProject, QgsVectorLayer, QgsTask, QgsApplication, QgsFeature, Qgis, QgsFeatureRequest, QgsGeometry)
from qgis.utils import iface
from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt.QtCore import QObject, pyqtSignal, QDate, QDateTime, QTime, QDir, QTemporaryFile

from . import DATA_SOURCE_REGISTRY, RELATION_VALUES_MAPPING_REGISTRY

downloaded_layers = []

from gissupport_plugin.tools.logger import Logger
from gissupport_plugin.tools.gisbox_connection import GISBOX_CONNECTION

class GisboxDataSource(QObject, Logger):
    """ Klasa bazowa dla źródeł danych GISBox """

    def __init__(self, data: dict, parent=None):
        super(GisboxDataSource, self).__init__(parent)
        self.name = data['name']
        self.display_name = data['verbose_name']
        self.attributes_schema = data['attributes_schema']
        self.geom_column_name = self.attributes_schema['geometry_name']
        self.id_column_name = self.attributes_schema['id_name']
        self.module = data['module']


class GisboxFeatureLayer(QObject, Logger):
    """ Bazowa klasa dla warstw wektorowych """

    on_reload = pyqtSignal()
    features_loaded = pyqtSignal(object)

    def __init__(self, data: dict, parent=None):
        super(GisboxFeatureLayer, self).__init__(parent)

        # Lista warstw dla danego typu
        self.parent = parent
        self.layers = []
        self.first = False

        self.datasource = None
        self.id = data['id']
        self.datasource_name = data['data_source_name']
        self.name = data['name']
        self.srid = data['srid']
        self.topo_layer = data['layer_scope'] in (
            'water', 'sewer') and not 'watermeters' in self.datasource_name
        self.geometry_type = 'multipoint' if self.name == 'water_watermeters' else data[
            'geometry_type']
        self.style = data['style_qgis']
        self.default_values = {}
        self.layer_scope = data.get('layer_scope')
        self.form_schema = data['form_schema']
        self.write_permission = data['write_permission']
        self.valid_fields = []
        self.filter_expression = data.get('filter_expression')
        self.relation_values_mapping = {}

        
        self.features_to_download = [] # id z gisbox
        self.features_to_delete = [] # id z qgis
        self.remove_all_features = False

        self.connectSignals()

    def _get_datasource(self, datasource_name: str) -> GisboxDataSource:
        """ Pobranie źródła danych """
        datasource = DATA_SOURCE_REGISTRY.get(datasource_name)
        if datasource is None:
            datasource_meta = GISBOX_CONNECTION.get(
                f'/api/dataio/data_sources/{datasource_name}/metadata?cache={time.time()}', sync=True)
            if not datasource_meta.get('data'):
                return
            datasource = GisboxDataSource(datasource_meta['data'])
            DATA_SOURCE_REGISTRY[datasource_name] = datasource
        return datasource

    def setLayer(self, layer=None, from_project=False):
        """ Rejestracja warstwy QGIS """
        if layer and not QgsProject.instance().layerTreeRoot().findLayers():
            self.first = True
        else:
            self.first = False
        if isinstance(self.sender(), QgsMapLayer):
            # Usunięcie warstwy z TOC
            try:
                self.layers.remove(self.sender())
            except ValueError:
                # Dla pierwszej wczytanej warstwy zwraca błąd,
                # który trzeba obsłużyć indywidualnie
                del self.layers[0]
            self.log(self.layers)
            self.unregisterLayer(self.sender())
        if not layer:
            return
        if self.datasource is None:
            self.datasource = self._get_datasource(self.datasource_name)
        # Ustawienia warstwy
        layer.setCustomProperty("skipMemoryLayersCheck", 1)
        layer.setCustomProperty('gisbox/layer_id', self.id)
        layer.setCustomProperty('gisbox/topological', self.topo_layer)
        layer.setCustomProperty('gisbox/is_gisbox_layer', True)
        layer.setCustomProperty('gisbox/layer_type', self.datasource_name)
        layer.setCustomProperty('gisbox/layer_scope', self.layer_scope)
        # Zarejestrowanie warstwy
        self.layers.append(layer)
        self.registerLayer(layer)
        if from_project:
            self._reload_layer_metadata()
        if layer is not None and len(self.layers) == 1:
            # Pobieranie obiektów warstwy (tylko za pierwszym razem)
            self.getFeatures()
        self.setLayerAttributeForm(layer, self.form_schema)

    def _validate_fields(self, form_schema: dict):
        elements = form_schema.get('elements')
        return [inner_element['attribute'] for element in elements for inner_element in element['elements']]

    def registerLayer(self, layer):
        """ Zarejestrowanie warstwy """
        # Odznaczenie pozycji w menu w przypadku usunięcia warstwy z QGIS
        layer.willBeDeleted.connect(self.setLayer)
        layer.beforeCommitChanges.connect(self.manageFeatures)
        layer.committedFeaturesAdded.connect(lambda _, added_features: self.getFeaturesIds(added_features))
        self.checkLayer(True)
        # Usunięcie z legendy ikony warstwy tymczasowej
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        indicators = iface.layerTreeView().indicators(node)
        if indicators:
            iface.layerTreeView().removeIndicator(node, indicators[0])

    def unregisterLayer(self, layer):
        """ Wyrejestrowanie warstwy """
        if not self.layers:
            self.checkLayer(False)
            pass
        try:
            layer.willBeDeleted.disconnect(self.setLayer)
        except Exception as e:
            self.log(e)

    def checkLayer(self, state):
        try:
            self.parent.setChecked(state)
        except:
            pass

    def zoomToExtent(self, layer):
        """ Przybiżenie do warstwy z innym układem współrzędnych """
        # Przybliżamy tylko do pierwszej dodanej warstwy
        if not self.first:
            return
        if layer.crs().authid() != QgsProject.instance().crs().authid():
            extent = layer.extent()
            fromCrs = QgsCoordinateReferenceSystem(layer.crs().authid())
            toCrs = QgsCoordinateReferenceSystem(
                QgsProject.instance().crs().authid())
            transformation = QgsCoordinateTransform(
                fromCrs, toCrs, QgsProject.instance())
            extent = transformation.transform(extent)
        else:
            extent = layer.extent()
        iface.mapCanvas().setExtent(extent.scaled(1.1))
        layer.triggerRepaint()
        self.first = False

    def connectSignals(self):
        """ Podłączanie sygnałów """
        self.on_reload.connect(self.onReload)

    def _reload_layer_metadata(self):
        self.datasource = self._get_datasource(self.datasource_name)
        self.fields = self.datasource.attributes_schema['attributes']
        if self.id:
            self.metadata = GISBOX_CONNECTION.get(f'/api/layers/features_layers/{self.id}', True)
            self.form_schema = self.metadata['data']['form_schema']
            self.valid_fields = self._validate_fields(
                form_schema=self.form_schema)

    def loadLayer(self, checked=False, group=None, toc_name=None):
        """ Wczytywanie warstwy do QGIS """

        if not toc_name:
            toc_name = self.name
        if self.layers:
            layer = self.layers[0].clone()
            layer.dataProvider().addFeatures(self.layers[0].getFeatures())
            layer.updateExtents(True)
        else:
            self._reload_layer_metadata()
            fields_table = []
            for field in self.fields:

                if field['name'] not in self.valid_fields:
                    continue

                data_type = field.get('data_type')
                if field['name'] == 'topogeom':
                    continue
                if field['name'] == self.datasource.geom_column_name:
                    continue
                if data_type.get('name', 'string') in ('decimal', 'float'):
                    fields_table.append('%s:real(20,%s)' % (
                        field['name'], field.get('decimal_places', 3)))
                elif data_type.get('name') in ('text', 'hyperlink'):
                    fields_table.append('%s:%s(%s)' %
                                        (field['name'], 'string',
                                         data_type.get("max_length", '-1') or '-1'))
                else:
                    fields_table.append('%s:%s' %
                                        (field['name'], field['data_type']['name']))
            qgis_fields = 'field=%s' % '&field='.join(
                fields_table)
            layer = QgsVectorLayer('%s?crs=epsg:%s&%s' % (
                self.geometry_type, self.srid, qgis_fields), toc_name, 'memory')
            self.message(f'Wczytywanie warstwy: {toc_name}...', duration=5)
            # Warstwa tylko do odczytu
            if self.topo_layer or self.layer_scope == 'module' or not self.write_permission:
                layer.setReadOnly(True)
        # Nadanie stylu - musi być przed set layer, ze wzgledu na to,
        # że nadanie stylu nadpisuje `customProperties` warstwy
        self.setStyle(layer)
        self.setLayer(layer)
        if group is None:
            QgsProject.instance().addMapLayer(layer)
        else:
            QgsProject.instance().addMapLayer(layer, False)
            group.addLayer(layer)
        layer.setName(toc_name)
        layer.reload()
        layer.triggerRepaint()
        
        self.deleteTemporaryIcons(layer)
        return layer

    def deleteTemporaryIcons(self, layer):
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        indicators = iface.layerTreeView().indicators(node)
        if indicators:
            iface.layerTreeView().removeIndicator(node, indicators[0])

    def setStyle(self, layer):
        """ Wczytanie stylu warstwy jeśli istnieje """
        if not self.style:
            return
        document = QDomDocument()
        document.setContent(self.style)
        layer.importNamedStyle(document)

    def getFeatures(self):
        """ Wysłanie żądania o obiekty warstwy """
        self.time = time.time()
        self.remove_all_features = True
  
        self.task = GisboxDownloadLayerTask(
            name=self.datasource_name,
            layer_id=self.id,
            gbfeaturelayer=self,
            payload={
                "data": {
                    "features_filter": self.filter_expression,
                    "style": {}
                }
            }
        )
        self.task.download_finished.connect(self.show_download_layer_success_message)
        QgsApplication.taskManager().addTask(self.task)

    def show_download_layer_success_message(self):
        self.message(
            f'Pomyślnie wczytano dane warstwy: {self.layers[0].name()}, czas: {time.time() - self.time}', level=Qgis.Success, duration=5)
    
    def onReload(self, *args, **kwargs):
        self.remove_all_features = True

        filter = self.filter_expression
        if self.features_to_download:
            filter = {
                        "$IN": {
                            self.datasource_name + '.' + self.datasource.id_column_name: {
                                "value": self.features_to_download
                            }
                        }
                    }
            self.remove_all_features = False

        self.task = GisboxDownloadLayerTask(
            name=self.datasource_name,
            layer_id=self.id,
            gbfeaturelayer=self,
            payload={
                "data": {
                    "features_filter": filter,
                    "style": {}
                }
            }
        )
        self.task.download_finished.connect(self.show_download_layer_success_message)
        QgsApplication.taskManager().addTask(self.task)

    def parseFeatures(self, temp_file: str):
        """ Parsowanie danych z serwera i dodanie obiektów do warstwy """
        try:
            new_features = self.gpkg2features(temp_file)
        except Exception as e:
            self.log(e)
            return
        
        layer = self.layers[0]
        if self.remove_all_features:
            # Czyścimy warstwę z obiektów (wymagane jeśli przeładowujemy istniejącą warstwę)
            layer.dataProvider().truncate()

        else:
            # Usuwamy dodane/edytowane obiekty z warstwy
            # a następnie dodajemy je od nowa ze wszystkimi wypełnionymi atrybutami z bazy 

            self.getFeaturesByDbIds(layer)
            if self.features_to_delete:
                layer.dataProvider().deleteFeatures(self.features_to_delete)

        # Dodanie obiektów do warstwy
        layer.dataProvider().addFeatures(new_features)
        # Aktualizacja zasięgu warstwy
        layer.updateExtents(True)
        self.zoomToExtent(layer)
        self.features_loaded.emit(layer)
        layer.reload()
        layer.triggerRepaint()
        self.features_to_download = []
        self.features_to_delete = []
        # Usunięcie zbędnego taska
        del self.task

    def gpkg2features(self, temp_file: str) -> Iterable[QgsFeature]:
        """ Przekształcenie warstwy GPKG na QgsFeature """
        # Stworzenie listy featerow warstwy
        # Zebranie nazw pól z warstwy qgis
        layer_fields = self.layers[0].fields()

        ds = ogr.Open(temp_file)
        lyr = ds.GetLayer()
        total = 50/lyr.GetFeatureCount()

        # Pasek postępu
        fields = self.datasource.attributes_schema['attributes']
        # Tworzymy obiekty przed pętlą ponieważ po `yield` są zapisywane w warstwie.
        # Późniejsze zmiany nie wpływają na zapisane obiekty
        geometry = QgsGeometry()
        new_feature = QgsFeature(layer_fields)
        # Iteracja po atrybutach sparsowanego obiektu
        for idx, feature in enumerate(lyr):
            # Sprawdzenie czy tabela ma geometrie
            try:
                # Geometria OGR -> QGIS, trochę wąskie gardło
                geometry.fromWkb( feature.GetGeometryRef().ExportToWkb() )
                new_feature.setGeometry(geometry)
            except AttributeError:
                # Brak geometrii
                pass

            for field in fields:
                field_name = field['name']
                
                if field_name not in self.valid_fields:
                    continue

                value = feature.GetField(field_name)
                if (relation:=field.get('relation')):
                    # dla atrybutów relacyjnych, v2 zwraca wartości atrybutów wyświetlanych
                    # musimy pozyskać wartości atrybutów zapisywanych
                    datasource = relation.get('data_source')
                    attribute = relation.get('attribute')
                    representation = relation.get('representation')
                    mapping_key = f'{datasource}{attribute}{representation}'
                    mapping = self.relation_values_mapping.get(mapping_key) or {}
                    value = mapping.get(value)

                new_feature.setAttribute(field_name, value)

            if hasattr(self, 'task'):
                try:
                    self.task.setProgress(idx*total+50)
                except RuntimeError:
                    continue

            yield new_feature
        del ds

    def setLayerAttributeForm(self, layer: QgsVectorLayer, form_schema: dict):

        config = layer.editFormConfig()
        id_field = layer.fields().indexFromName(self.datasource.id_column_name)
        layer.setFieldAlias(id_field, 'Identyfikator')
        config.setReadOnly(id_field, True)

        if form_schema:
            elements = form_schema.get('elements')

            if elements is None:
                return

            field_id_map = {field.name(): field_id for field_id,
                            field in enumerate(layer.fields())}

            config.clearTabs()
            config.setLayout(QgsEditFormConfig.TabLayout)

            for element in elements:
                tab = QgsAttributeEditorContainer(element['label'], None)
                tab.setIsGroupBox(False)

                for idx, inner_element in enumerate(element['elements']):

                    attr = inner_element['attribute']
                    label = inner_element.get('label', '')

                    field_id = field_id_map.get(attr)
                    if field_id:
                        layer.setFieldAlias(field_id, label)

                        if inner_element.get('required', False) == True and not field_id == id_field:
                            layer.setFieldConstraint(
                                field_id,
                                QgsFieldConstraints.ConstraintNotNull,
                                QgsFieldConstraints.ConstraintStrengthHard,
                            )

                    default_value_policy = inner_element.get(
                        'default_value_policy')
                    if default_value_policy:
                        self.default_values[attr] = default_value_policy['value']

                    tab.addChildElement(
                        QgsAttributeEditorField(attr, idx, tab))
                config.addTab(tab)

        attributes = self.datasource.attributes_schema['attributes']

        for attribute in attributes:
            field_id = layer.fields().indexFromName(attribute['name'])
            config.setReadOnly(field_id, attribute.get('read_only'))
            attribute_type = attribute.get('type')

            if attribute_type == 'dict':
                allowed_values = attribute.get('allowed_values')
                if allowed_values:
                    dict_values = {value: value for value in allowed_values}
                    self.setWidgetType(layer, dict_values, field_id)
            elif attribute_type == 'relation':
                if 'parent' in attribute['name']:
                    continue
                relation = attribute.get('relation')
                related_datasource = relation.get('data_source')
                related_attribute = relation.get('attribute')
                representation = relation.get('representation')
                if related_datasource and representation:
                    relation_map_values = RELATION_VALUES_MAPPING_REGISTRY.get(
                        related_datasource, {}).get(related_attribute, {}).get(representation)
                    dict_values = {data['text']: data['value']
                                   for data in relation_map_values}
                    if dict_values:
                        # zapisujemy mapowanie atrybutów relacyjnych dla metody tworzenia obiektów w warstwie
                        self.relation_values_mapping[related_datasource + related_attribute + representation] = dict_values
                        self.setWidgetType(layer, dict_values, field_id)

        layer.setEditFormConfig(config)

    def setWidgetType(self, layer: QgsVectorLayer, dict_values: dict, field_id: int):
        """ Ustawianie typu atrybutu w formularzu atrybutów """
        value_map = [{"": NULL}]
        value_map.extend({str(text): str(value)} for text, value in dict_values.items())
        setup = QgsEditorWidgetSetup(
            'ValueMap', {'map': value_map})
        layer.setEditorWidgetSetup(field_id, setup)

    def getFeaturesDbIds(self, qgis_ids, layer):
        return [f[self.datasource.id_column_name] for f in layer.dataProvider().getFeatures( QgsFeatureRequest().setFilterFids( qgis_ids ))]

    def getFeaturesByDbIds(self, layer):
        expression = f"\"{self.datasource.id_column_name}\" IN ({', '.join(map(str, self.features_to_download))})"
        request = QgsFeatureRequest().setFilterExpression(expression)
        features = layer.getFeatures(request)
        for feature in features:
            self.features_to_delete.append(feature.id())

    def getFeaturesIds(self, added_features: List[QgsFeature]):
        for feature in added_features:
            self.features_to_delete.append(feature.id())

    def manageFeatures(self):
        layer = self.sender()
        edit_buffer = layer.editBuffer()

        payload = {'data_source_name': self.datasource_name, 'layer_id': self.id}

        to_add = self.addFeatures(edit_buffer)
        if to_add:
            payload['insert'] = to_add

        to_update = self.updateFeatures(layer, edit_buffer)
        if to_update:
            payload['update'] = to_update

        to_delete = self.deleteFeatures(layer, edit_buffer)
        if to_delete:
            payload['delete'] = to_delete

        if to_delete:
            payload['delete']['features_ids'] = self.getFeaturesDbIds(
                to_delete['qgis_features_ids'], layer)

        GISBOX_CONNECTION.post(
            f"/api/dataio/data_sources/{self.datasource_name}/features/edit?layer_id={self.id}",
            {"data": payload}, callback=self.afterModify, sync=True
        )
    
    def afterModify(self, data: Dict[str, Any]):
        if data.get("error"):
            self.message(data.get("error_message"), level=Qgis.Critical)
            return
        
        modified_data = data.get("data")
        if modified_data.get("delete") and not modified_data.get("insert") and not modified_data.get("update"):
            # jeśli tylko usuwamy obiekty z warstwy, nie musimy jej przeładowywać
            return

        if modified_data.get("insert"):
            self.features_to_download.extend([f[self.datasource.id_column_name] for f in modified_data["insert"]])

        if modified_data.get("update"):
            db_ids = [f['properties'][self.datasource.id_column_name]  for f in modified_data["update"]]
            self.features_to_download.extend(db_ids)

        self.message(f'Pomyślnie zmodyfikowano dane warstwy: {self.layers[0].name()}', 
                        level=Qgis.Success, duration=5)
        self.on_reload.emit()
        
    def addFeatures(self, edit_buffer):
        """ Dodanie nowych obiektów do warstwy użytkownika """
        added_features = edit_buffer.addedFeatures().values()

        features_data = []

        for feature in added_features:
            if feature.hasGeometry():
                f = feature.__geo_interface__
                if f['geometry']['type'].lower() != self.geometry_type.lower():
                    f['geometry']['type'] = self.geometry_type
                    f['geometry']['coordinates'] = [f['geometry']['coordinates']]
                properties = {k: self.sanetize_data_type(v) if v != NULL else None for k,
                              v in f['properties'].items()}
                geometry = f['geometry']
                geometry.update({'crs': {
                    'type': 'name',
                    'properties': {
                        'name': f'EPSG:{self.srid}'
                    }
                }})
                properties.update({self.datasource.geom_column_name: geometry})
                features_data.append(properties)
            else:
                attributes = feature.attributes()
                names = feature.fields().names()
                properties = {names[i]: self.sanetize_data_type(attributes[i]) if attributes[i] != NULL else None
                              for i in range(len(names))}

                features_data.append(properties)

        return features_data

    def deleteFeatures(self, layer, edit_buffer):
        qgis_deleted_features_ids = edit_buffer.deletedFeatureIds()
        if not qgis_deleted_features_ids:
            return {}

        return {'qgis_features_ids': qgis_deleted_features_ids}

    def updateFeatures(self, layer, edit_buffer):
        changed_attributes = edit_buffer.changedAttributeValues()
        changed_geometries = edit_buffer.changedGeometries()

        fids = list(set(list(changed_attributes.keys()) +
                    list(changed_geometries.keys())))

        features = []

        for feature in layer.getFeatures(fids):
            if feature.hasGeometry():
                f = feature.__geo_interface__
                if f['geometry']['type'].lower() != self.geometry_type.lower():
                    f['geometry']['type'] = self.geometry_type
                    f['geometry']['coordinates'] = [f['geometry']['coordinates']]
                properties = {k: self.sanetize_data_type(v) if v != NULL else None for k,
                              v in f['properties'].items()}
                geometry = f['geometry']
                geometry.update({'crs': {
                    'type': 'name',
                    'properties': {
                        'name': f'EPSG:{self.srid}'
                    }
                }})
                properties.update({self.datasource.geom_column_name: geometry})

                features.append({
                    'properties': properties,
                    'fid': f['properties'].pop(self.datasource.id_column_name),
                    'qgis_id': feature.id()
                })

            else:
                attributes = feature.attributes()
                names = feature.fields().names()
                properties = {names[i]: self.sanetize_data_type(attributes[i]) if attributes[i] != NULL else None
                              for i in range(len(names))}

                features.append({
                    'properties': properties,
                    'fid': properties[self.datasource.id_column_name],
                    'qgis_id': feature.id()
                })

        return features
    
    def sanetize_data_type(self, value: Any) -> Any:
        if isinstance(value, QDateTime):
            value = value.toString('yyyy-MM-dd hh:mm:ss')
        elif isinstance(value, QDate):
            value = value.toString('yyyy-MM-dd')
        elif isinstance(value, QTime):
            value = value.toString('hh:mm:ss')
        return value


class GisboxDownloadLayerTask(QgsTask, Logger):
    download_finished = pyqtSignal(bool)

    def __init__(self, name: str, layer_id: int, payload: dict, gbfeaturelayer: GisboxFeatureLayer):
        self.layer_id = layer_id
        self.name = name
        self.endpoint = f'/api/v2/datasources-download/{self.name}?format=gpkg&layer_id={self.layer_id}&attributes_use_verbose_names=false'
        self.payload = payload
        self.network_manager = GISBOX_CONNECTION.MANAGER.instance()
        self.gbfeaturelayer = gbfeaturelayer
        self.download_progress = 0
        self.first_process_id = None
        super().__init__('Wczytywanie warstwy', QgsTask.CanCancel)

    def run(self):
        request = GISBOX_CONNECTION._createRequest(self.endpoint)
        request.setRawHeader(b"Accept-Encoding", b"identity")

        data = json.dumps(self.payload).encode()
        self.network_manager.downloadProgress.connect(self.set_download_progress)

        reply = self.network_manager.blockingPost(request, data)

        # Tworzymy plik tymczasowy, XXXXXX będzie zastąpione losowymi znakami
        tmp_file = QTemporaryFile( f"{QDir.tempPath()}/XXXXXX.gpkg" )
        # Zapis danych do pliku
        tmp_file.open()
        tmp_file.write(reply.content())
        del reply
        tmp_file.close()
        self.gbfeaturelayer.parseFeatures(tmp_file.fileName())
        # Usunięcie pliku z dysku
        tmp_file.remove()
        tmp_file.deleteLater()


        self.download_finished.emit(True)
        if self.layer_id not in downloaded_layers:
            downloaded_layers.append(self.layer_id)
        return True
    
    def set_download_progress(self, id: int, bytesReceived: int, bytesTotal: int):
        if self.first_process_id is None:
            self.first_process_id = id
        # przy pierwszym pobieraniu warstwy, aktualizujemy status trzecim procesem (faktycznym pobieraniem danych)
        skip_processes = 2
        # przy kolejnym pobieraniu tej samej warstwy, korzystamy z drugiego procesu
        if self.layer_id in downloaded_layers:
            skip_processes = 1
        if id == self.first_process_id + skip_processes:
            if bytesTotal in (0, -1):
                self.setProgress(0)
            else:
                download_progress = bytesReceived / bytesTotal * 50
                if download_progress > self.download_progress:
                    self.download_progress = download_progress
                self.setProgress(self.download_progress)

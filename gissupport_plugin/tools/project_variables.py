import json
from typing import Dict, Any

from qgis.core import QgsProject, QgsVectorLayer

LAYER_MAPPINGS_KEY = "gisbox/layer_mappings"


def get_project_variables() -> Dict[Any, Any]:
    """
    Zwraca wszystkie zmienne zapisane w aktywnym projekcie
    """
    project = QgsProject.instance()
    custom_variables = project.customVariables()
    return custom_variables

def save_project_variables(custom_variables: Dict[Any, Any]):
    """
    Zapisuje zmienne w aktywnym projekcie
    """
    project = QgsProject.instance()
    project.setCustomVariables(custom_variables)
    return

def get_layer_mappings() -> Dict[str, int]:
    """
    Pobiera mapowania ID warstw GIS.Box z aktywnego projektu
    """
    custom_variables = get_project_variables()
    stored_mappings = custom_variables.get(LAYER_MAPPINGS_KEY) or ''
    mappings = json.loads(stored_mappings) if stored_mappings else {}
    return mappings

def save_layer_mappings(mappings = Dict[str, int]):
    """
    Zapisuje mapowania ID warstw GIS.Box w aktywnym projekcie
    """
    custom_variables = get_project_variables()
    custom_variables[LAYER_MAPPINGS_KEY] = json.dumps(mappings)
    save_project_variables(custom_variables)

def save_layer_mapping(layer_qgis_id: str, layer_gisbox_id: int):
    """ Dodaje mapowanie do zmiennej projektu z mapowaniami """
    layer_mappings = get_layer_mappings()

    if layer_qgis_id in layer_mappings:
        mapped_id = layer_mappings[layer_qgis_id]
        if layer_gisbox_id == mapped_id:
            return
    
    layer_mappings[layer_qgis_id] = layer_gisbox_id

    save_layer_mappings(layer_mappings)
    return

def get_layer_mapping(layer_qgis_id: str) -> int:
    """ Zwraca ID konkretnej warstwy z GIS.Box, zapisane w zmiennych projektu """

    layer_mappings = get_layer_mappings()
    layer_gisbox_id = layer_mappings.get(layer_qgis_id, -1)

    return int(layer_gisbox_id)


def remove_layer_mapping(layer_qgis_id: str):
    """ Usuwa mapowanie ze zmiennej projektu z mapowaniami """

    layer_mappings = get_layer_mappings()

    if layer_qgis_id in layer_mappings:
        del layer_mappings[layer_qgis_id]
        save_layer_mappings(layer_mappings)

    return

def migrate_layer_gisbox_id_variable(layer: QgsVectorLayer):
    """ Przenosi ID warstwy z GIS.Box ze zmiennych warstwy do zmiennych projektu """

    layer_gisbox_id = layer.customProperty('gisbox/layer_id')

    if layer_gisbox_id:
        layer.removeCustomProperty('gisbox/layer_id')
        layer.removeCustomProperty('gisbox/is_gisbox_layer')
        save_layer_mapping(layer_qgis_id=layer.id(), layer_gisbox_id=layer_gisbox_id)

    return
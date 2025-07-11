import json
from typing import Dict, Any

from qgis.core import QgsProject

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
    
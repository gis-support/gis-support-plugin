from pathlib import Path
import tempfile
import os
from typing import Dict, Any

from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsIconUtils, QgsProject


class GpkgHandler:
    """
    Klasa obsługująca pliki GPKG przed ich importem do Usemaps Lite.
    """

    def __init__(self):
        pass

    def get_layer_info(self, gpkg_file_path: str) -> Dict[str, Any]:
        """
        Zwraca informacje o warstwach znajdujących się we wgrywanym pliku .gpkg
        """

        layer_info = []

        path = Path(gpkg_file_path)
        layer = QgsVectorLayer(str(path), "layer", "ogr")
        layers = layer.dataProvider().subLayers()
        
        for sub in layers:
            name = sub.split('!!::!!')[1]
            temppath = f"{str(path)}|layername={name}"
            templayer = QgsVectorLayer(temppath, name, "ogr")
            geom_type = templayer.geometryType()
            icon = QgsIconUtils.iconForGeometryType(geom_type)
            
            layer_info.append({
                "name": name,
                "icon": icon
            })
            
        return layer_info

    def extract_layer_to_temp_gpkg(self, source_uri: str, selected_layer_name: str):
        """
        Wyciąga warstwę z podanego URI do tymczasowego pliku GeoPackage.
        """

        source_layer = QgsVectorLayer(source_uri, selected_layer_name, "ogr")

        if not source_layer.isValid():
            return None, f"Nie udało się wczytać warstwy ze wskazanego URI: {source_uri}"

        sanitized_layer_name = "".join(c for c in selected_layer_name if c.isalnum() or c in (' ', '_', '-')).strip()
        temp_gpkg_filename = f"{sanitized_layer_name}.gpkg"
        temp_gpkg_path = os.path.join(tempfile.gettempdir(), temp_gpkg_filename)

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.fileEncoding = "UTF-8"

        transform_context = QgsProject.instance().transformContext()

        QgsVectorFileWriter.writeAsVectorFormatV3(
            source_layer,
            temp_gpkg_path,
            transform_context,
            options
        )

        return temp_gpkg_path

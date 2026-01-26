from pathlib import Path
import tempfile
import os
from typing import Dict, Any

from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsIconUtils, QgsProject, QgsWkbTypes, QgsFields, QgsFeature
from qgis.utils import iface


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

    def save_layer_to_temp_gpkg(self, layer: QgsVectorLayer) -> str:
        if not layer or not layer.isValid():
            return None

        sanitized_name = "".join(c for c in layer.name() if c.isalnum() or c in (' ', '_', '-')).strip()
        temp_path = Path(tempfile.gettempdir(), f"{sanitized_name}.gpkg")

        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

        # Tworzenie nowej warstwy tymczasowej bez pól ID
        geom_type_name = QgsWkbTypes.displayString(layer.wkbType())
        temp_layer = QgsVectorLayer(
            f"{geom_type_name}?crs={layer.crs().authid()}",
            "temp",
            "memory"
        )
        temp_provider = temp_layer.dataProvider()

        # Kopiowanie pól, które nie są ID
        blacklisted = {'fid', '_id', 'id'}
        fields_to_copy = QgsFields()

        for field in layer.fields():
            if field.name().lower() not in blacklisted:
                fields_to_copy.append(field)

        temp_provider.addAttributes(fields_to_copy)
        temp_layer.updateFields()

        # Kopiowanie obiektów bez pól ID
        new_features = []
        for feature in layer.getFeatures():
            new_feat = QgsFeature(fields_to_copy)

            attrs = []
            for field in fields_to_copy:
                attrs.append(feature[field.name()])

            new_feat.setAttributes(attrs)
            new_feat.setGeometry(feature.geometry())
            new_features.append(new_feat)

        temp_provider.addFeatures(new_features)

        # Zapis czystej warstwy bez żadnych pól ID
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.fileEncoding = "UTF-8"
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

        error_code, _, _, error_msg = QgsVectorFileWriter.writeAsVectorFormatV3(
            temp_layer,
            str(temp_path),
            QgsProject.instance().transformContext(),
            options
        )

        if error_code == QgsVectorFileWriter.NoError:
            return temp_path
        else:
            iface.messageBar().pushCritical(
                "Usemaps Lite",
                f"Błąd eksportu warstwy {layer.name()}: {error_msg}"
            )
            return
import requests

URL = r"https://testing.qgis-api.apps.divi.pl/lpis_bbox"

def search(parcel_id, key):
    url = "{}/{}".format(URL, parcel_id)
    params = {"key": key}
    response = requests.get(url, params=params)
    parcels = response.json()
    return parcels

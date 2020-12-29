import requests

URL = r"https://testing.qgis-api.apps.divi.pl/lpis_bbox"

def search(parcel_id):
    url = "{}/{}".format(URL, parcel_id)
    response = requests.get(url)
    parcels = response.json()
    return parcels

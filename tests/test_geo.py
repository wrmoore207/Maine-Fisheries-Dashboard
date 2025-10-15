# tests/test_geo.py
from pathlib import Path

def test_lobster_geojson_present():
    assert Path("data/geo/lobster_zones.geojson").exists(), \
        "Provide the lobster zones GeoJSON at data/geo/lobster_zones.geojson"

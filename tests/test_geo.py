# tests/test_geo.py
from pathlib import Path

def test_lobster_geojson_present():
    assert Path("data/geo/lobster_zones.geojson").exists(), \
        "Provide the lobster zones GeoJSON at data/geo/lobster_zones.geojson"

from pathlib import Path
import json
import pandas as pd

def test_geojson_exists():
    p = Path("data/geo/lobster_zones.geojson")
    assert p.exists(), "Lobster zones GeoJSON missing."

def test_zone_join_keys_unique():
    p = Path("data/geo/lobster_zones.geojson")
    gj = json.loads(p.read_text(encoding="utf-8"))
    keys = []
    for feat in gj.get("features", []):
        props = feat.get("properties", {})
        z = props.get("ZONE") or props.get("zone") or props.get("Zone") or props.get("ZONE_ID")
        if z is not None:
            keys.append(str(z).strip())
    assert len(keys) == len(set(keys)), "Zone keys in GeoJSON should be unique."

#!/usr/bin/env python3
"""
Build data/geo/ports.csv by geocoding Maine ports with Nominatim (OpenStreetMap).

Usage:
  python scripts/build_ports_csv.py

Notes:
- Respects Nominatim rate limit (>=1 sec/request).
- Skips synthetic buckets like "Other Cumberland".
- Writes:
    data/geo/ports.csv           (port,port_lat,port_lon)
    data/geo/ports_missing.csv   (ports we couldn't resolve)
"""

from __future__ import annotations
import os
import re
import time
import json
import csv
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import requests

# -----------------------
# Configuration
# -----------------------
OUTPUT_DIR = Path("data/geo")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUTPUT_DIR / "ports.csv"
OUT_MISSING = OUTPUT_DIR / "ports_missing.csv"
LOG_JSON = OUTPUT_DIR / "ports_geocode_log.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Maine-ish bounding box: (min_lon, min_lat, max_lon, max_lat)
VIEWBOX = (-71.1, 42.9, -66.8, 47.5)

# IMPORTANT: set a real contact email in env or edit this string
CONTACT_EMAIL = os.getenv("NOMINATIM_EMAIL", "your-email@example.com")

HEADERS = {
    "User-Agent": f"GOM-Fisheries-Dashboard/1.0 ({CONTACT_EMAIL})"
}

# Skip synthetic categories
SKIP_PATTERNS = [
    r"^Other\s",           # Other Cumberland, Other Maine, ...
]

# Optional manual overrides for tricky places (if you know exact coords, add them here)
# Example format: "Monhegan": (43.7642, -69.3214)
MANUAL_OVERRIDES: Dict[str, Tuple[float, float]] = {
    # "Monhegan": (43.7642, -69.3214),
}

# Your provided list (exact)
PORTS: List[str] = [
    'Addison', 'Arrowsic', 'Bailey Island', 'Bar Harbor', 'Bass Harbor', 'Beals', 'Belfast',
    'Bernard', 'Biddeford', 'Biddeford Pool', 'Birch Harbor', 'Blue Hill', 'Boothbay',
    'Boothbay Harbor', 'Bremen', 'Bristol', 'Brooklin', 'Brooksville', 'Brunswick',
    'Bucks Harbor', 'Bunkers Harbor', 'Camden', 'Cape Elizabeth', 'Cape Porpoise',
    'Castine', 'Chebeague Island', 'Corea', 'Cranberry Isles', 'Cundys Harbor', 'Cushing',
    'Cutler', 'Damariscotta', 'Deer Isle', 'Eastport', 'Edgecomb', 'Edmunds', 'Eliot',
    'Ellsworth', 'Falmouth', 'Five Islands', 'Franklin', 'Freeport', 'Frenchboro',
    'Friendship', 'Georgetown', 'Gouldsboro', 'Hancock', 'Harpswell', 'Harrington',
    'Isle au Haut', 'Islesboro', 'Jonesboro', 'Jonesport', 'Kennebunk', 'Kennebunkport',
    'Kittery', 'Lamoine', 'Lincolnville', 'Little Deer Isle', 'Long Island', 'Lubec',
    'Machias', 'Machiasport', 'Matinicus', 'Milbridge', 'Monhegan', 'Mount Desert',
    'New Harbor', 'Newcastle', 'North Haven', 'Northeast Harbor', 'Ogunquit',
    'Other Cumberland', 'Other Hancock', 'Other Maine', 'Other Sagadahoc', 'Other Waldo',
    'Other Washington', 'Other York', 'Owls Head', 'Pemaquid', 'Pembroke', 'Penobscot',
    'Perry', 'Phippsburg', 'Pine Point', 'Port Clyde', 'Portland', 'Prospect Harbor',
    'Robbinston', 'Rockland', 'Rockport', 'Roque Bluffs', 'Round Pond', 'Saco',
    'Scarborough', 'Seal Cove', 'Seal Harbor', 'Searsport', 'Sebasco', 'Sedgwick',
    'Sheepscot', 'Sorrento', 'South Bristol', 'South Gouldsboro', 'South Thomaston',
    'Southport', 'Southwest Harbor', 'Spruce Head', 'St. George', 'Steuben',
    'Stockton Springs', 'Stonington', 'Sullivan', 'Surry', 'Swans Island', 'Tenants Harbor',
    'Thomaston', 'Tremont', 'Trenton', 'Trescott', 'Vinalhaven', 'Waldoboro', 'Warren',
    'Wells', 'West Bath', 'West Point', 'Westport Island', 'Whiting', 'Winter Harbor',
    'Wiscasset', 'Woolwich', 'Yarmouth', 'York', 'York Harbor'
]

# -----------------------
# Helpers
# -----------------------
def should_skip(name: str) -> bool:
    return any(re.search(p, name, flags=re.I) for p in SKIP_PATTERNS)

def norm_query(name: str) -> str:
    # Prefer explicit Maine/USA context; small tweak for known villages/islands
    return f"{name}, Maine, USA"

def geocode(name: str) -> Optional[Tuple[float, float, Dict[str, Any]]]:
    # Manual override first
    if name in MANUAL_OVERRIDES:
        lat, lon = MANUAL_OVERRIDES[name]
        return lat, lon, {"source": "manual_override"}

    params = {
        "q": norm_query(name),
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "countrycodes": "us",
        "viewbox": f"{VIEWBOX[0]},{VIEWBOX[1]},{VIEWBOX[2]},{VIEWBOX[3]}",
        "bounded": 1,
    }
    try:
        r = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        item = data[0]
        lat = float(item["lat"])
        lon = float(item["lon"])
        return lat, lon, item
    except Exception as e:
        return None

# -----------------------
# Main
# -----------------------
def main():
    resolved = []
    missing = []
    log = {}

    print("Geocoding Maine ports with Nominatim…")
    for i, name in enumerate(PORTS, 1):
        if should_skip(name):
            print(f"SKIP [{i}/{len(PORTS)}]: {name}")
            missing.append({"port": name, "reason": "synthetic_bucket"})
            continue

        print(f"LOOKUP [{i}/{len(PORTS)}]: {name}")
        res = geocode(name)
        if res is None:
            print(f"  -> NOT FOUND")
            missing.append({"port": name, "reason": "not_found"})
        else:
            lat, lon, raw = res
            display = raw.get("display_name", "")
            print(f"  -> {lat:.5f}, {lon:.5f}  ({display})")
            resolved.append({"port": name, "port_lat": lat, "port_lon": lon})
            log[name] = raw

        # Respect rate-limits
        time.sleep(1.1)

    # Write outputs
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["port", "port_lat", "port_lon"])
        w.writeheader()
        for row in resolved:
            w.writerow(row)

    with OUT_MISSING.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["port", "reason"])
        w.writeheader()
        for row in missing:
            w.writerow(row)

    with LOG_JSON.open("w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

    print(f"\n✅ Wrote {len(resolved)} ports to {OUT_CSV}")
    print(f"🟨 Missing/Skipped: {len(missing)} → {OUT_MISSING}")
    print(f"📝 Raw geocode log: {LOG_JSON}")

if __name__ == "__main__":
    main()

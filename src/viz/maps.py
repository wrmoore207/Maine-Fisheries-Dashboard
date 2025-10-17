from __future__ import annotations
import json, re
from pathlib import Path
import pandas as pd
import pydeck as pdk

def load_geojson(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _detect_zone_prop(geojson: dict) -> str | None:
    """Heuristic to find which property holds the zone identifier."""
    feats = geojson.get("features", [])
    common = ["ZONE", "zone", "Zone", "ZONE_ID", "LOB_ZONE", "lob_zone", "LobZone"]
    # try common keys first if any feature has a value
    for k in common:
        for f in feats[:50]:
            if k in (f.get("properties") or {}):
                return k
    # otherwise just pick the first string-like property we see
    for f in feats[:50]:
        for k, v in (f.get("properties") or {}).items():
            if isinstance(v, (str, int)):
                return k
    return None

_letter_re = re.compile(r"[A-Za-z]")

def _normalize_zone_value(val) -> tuple[str | None, str]:
    """
    Convert a zone property value into a single uppercase letter A..G (for joining)
    and a human-friendly label for the tooltip.
    Returns (zone_letter, label).
    """
    if val is None:
        return None, "No data"
    s = str(val).strip()
    # 1) if it contains any letter, take the first letter
    m = _letter_re.search(s)
    if m:
        letter = m.group(0).upper()
        return letter, f"Zone {letter}"
    # 2) numeric -> map 1..7 to A..G
    try:
        n = int(float(s))
        if 1 <= n <= 7:
            letter = chr(ord("A") + (n - 1))
            return letter, f"Zone {letter}"
    except Exception:
        pass
    # 3) fallback
    return None, s

def render_lobster_zone_map(
    df_zone_yoy: pd.DataFrame,
    geojson: dict,
    zone_prop: str | None = None,
):
    # --- build DF lookup ---
    df_lookup = {
        str(z).strip().upper(): row
        for z, row in df_zone_yoy.set_index("zone").to_dict(orient="index").items()
    }

    zprop = zone_prop or _detect_zone_prop(geojson) or "ZONE"

    # RGBA color table
    COLOR = {
        "increase":     [34, 139, 34, 180],   # green
        "decrease":     [178, 34, 34, 180],   # red
        "no_change":    [120, 120, 120, 160], # gray
        "no_baseline":  [200, 200, 200, 120], # light gray
        "no_data":      [200, 200, 200, 120], # light gray
    }

    matched = unmatched = 0
    for feat in geojson.get("features", []):
        props = (feat.get("properties") or {}).copy()
        raw = props.get(zprop)
        letter, label = _normalize_zone_value(raw)

        props["zone_label"]  = label
        props["zone_letter"] = letter

        row = df_lookup.get(letter) if letter else None
        if row:
            matched += 1
            cat = row.get("category", "no_data")
            props["yoy_pct"]   = row.get("yoy_pct", None)
            props["yoy_label"] = row.get("yoy_label", "No baseline")
            props["category"]  = cat
            props["fill_color"] = COLOR.get(cat, COLOR["no_data"])
        else:
            unmatched += 1
            props["yoy_pct"]   = None
            props["yoy_label"] = "No data"
            props["category"]  = "no_data"
            props["fill_color"] = COLOR["no_data"]

        feat["properties"] = props

    layer = pdk.Layer(
        "GeoJsonLayer",
        geojson,
        opacity=0.65,
        stroked=True,
        filled=True,
        get_fill_color="properties.fill_color",   # <-- direct accessor, no expression
        get_line_color=[40, 40, 40, 200],
        line_width_min_pixels=1.5,
        pickable=True,
    )

    view_state = pdk.ViewState(latitude=44.3, longitude=-69.0, zoom=6.2)
    tooltip = {
        "html": "<b>Zone:</b> {zone_label}<br/><b>YOY:</b> {yoy_label}<br/><b>Status:</b> {category}",
        "style": {"backgroundColor": "rgba(30,30,30,0.9)", "color": "white"},
    }

    deck = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip, map_style=None)
    deck._gom_debug = {"zone_prop_used": zprop, "matched_features": matched, "unmatched_features": unmatched}
    return deck

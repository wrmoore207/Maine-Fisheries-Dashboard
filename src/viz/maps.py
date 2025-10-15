# src/viz/maps.py
from __future__ import annotations
from pathlib import Path
import json
import pandas as pd
import plotly.express as px

# Try to detect which property in the GeoJSON holds the zone label.
def _detect_zone_property(geojson: dict) -> str:
    for f in geojson.get("features", [])[:10]:
        props = (f or {}).get("properties", {}) or {}
        for k, v in props.items():
            if "zone" in k.lower():
                s = str(v).strip().upper()
                if s in list("ABCDEFG"):
                    return k
    # fallback: common names
    for k in ("ZONE", "Zone", "LOB_ZONE", "lob_zone"):
        if k in (geojson.get("features", [{}])[0].get("properties", {}) or {}):
            return k
    raise KeyError("Could not detect a zone property in GeoJSON (looked for *zone* keys).")

def lobster_zone_map(
    df: pd.DataFrame,
    metric: str = "weight",  # or "value", "trips", "harvesters"
    geojson_path: str | Path = "data/geo/lobster_zones.geojson",
    title: str | None = None,
):
    """
    Build a choropleth for lobster zones A–G keyed on df['lob_zone'].
    Expects df already filtered (e.g., by year).
    """
    if df.empty:
        return None

    # Normalize zones in your data to single letters A–G
    dfn = df.copy()
    dfn["lob_zone"] = dfn["lob_zone"].astype(str).str.strip().str.upper()
    dfn = dfn[dfn["lob_zone"].isin(list("ABCDEFG"))]

    # Aggregate by zone for the chosen metric
    metric_map = {
        "weight": ("weight", "sum"),
        "value": ("value", "sum"),
        "trips": ("trip_n", "sum"),
        "harvesters": ("harv_n", "sum"),
    }
    if metric not in metric_map:
        raise ValueError(f"metric must be one of {list(metric_map)}")
    col, how = metric_map[metric]

    zone_df = (
        dfn.groupby("lob_zone", dropna=False)
           .agg(**{metric: (col, how)})
           .reset_index()
    )

    if zone_df.empty:
        return None

    # Load geojson and ensure it exposes a comparable property
    gj_path = Path(geojson_path)
    if not gj_path.exists():
        raise FileNotFoundError(f"GeoJSON not found at {gj_path}")
    gj = json.loads(gj_path.read_text(encoding="utf-8"))

    zone_prop = _detect_zone_property(gj)

    # Create a synthetic, uniform property 'lob_zone' (A–G) in the geojson
    for feat in gj.get("features", []):
        z = str(feat.get("properties", {}).get(zone_prop, "")).strip().upper()
        feat["properties"]["lob_zone"] = z  # harmonize name

    # Plotly choropleth
    fig = px.choropleth(
        zone_df,
        geojson=gj,
        locations="lob_zone",
        color=metric,
        featureidkey="properties.lob_zone",
        projection="mercator",
        hover_name="lob_zone",
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0),
        title=title or f"{metric.capitalize()} by Lobster Zone",
        coloraxis_colorbar=dict(title=metric.capitalize()),
    )
    return fig

from __future__ import annotations
import json
import pandas as pd
import streamlit as st
import pydeck as pdk
from pathlib import Path

# ---------- Shared ----------
@st.cache_data
def load_geojson(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _metric_options(df: pd.DataFrame) -> list[str]:
    base = ["value"]
    if "revenue_usd" in df.columns:
        base.append("revenue_usd")
    return base

# ---------- ZONE (lobster) ----------
def zone_totals(df: pd.DataFrame, metric: str = "value") -> pd.DataFrame:
    if "zone" not in df.columns:
        return pd.DataFrame(columns=["zone", "metric_total"])
    if df["zone"].dropna().empty:
        return pd.DataFrame(columns=["zone", "metric_total"])
    gp = df.dropna(subset=["zone"]).groupby("zone", dropna=True)[metric].sum().reset_index()
    gp.columns = ["zone", "metric_total"]
    return gp

def _choropleth_layer(geojson: dict, zone_df: pd.DataFrame):
    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        z = props.get("ZONE") or props.get("zone") or props.get("Zone") or props.get("ZONE_ID")
        props["__zone_key__"] = str(z).strip() if z is not None else None

    join = zone_df.copy()
    join["__zone_key__"] = join["zone"].astype(str).str.strip()

    totals = {r["__zone_key__"]: float(r["metric_total"]) for _, r in join.iterrows()}
    max_val = max(totals.values()) if totals else 1.0

    for feat in geojson.get("features", []):
        z = feat["properties"].get("__zone_key__")
        val = totals.get(z, 0.0)
        feat["properties"]["metric_total"] = val
        intensity = 30 + int(200 * (val / max_val)) if max_val > 0 else 30
        feat["properties"]["fill_color"] = [15, 108, 141, min(255, intensity + 25)]

    return pdk.Layer(
        "GeoJsonLayer",
        geojson,
        opacity=0.7,
        stroked=True,
        filled=True,
        get_fill_color="properties.fill_color",
        get_line_color=[40, 40, 40],
        lineWidthMinPixels=1,
        pickable=True,
        auto_highlight=True,
    )

def render_zone_map(df: pd.DataFrame, geojson_path: str | Path, metric: str = "value"):
    zdf = zone_totals(df, metric=metric)
    if zdf.empty:
        st.info("No zone-level data available to map for the current selection.")
        return
    gj = load_geojson(geojson_path)
    view_state = pdk.ViewState(latitude=44.2, longitude=-68.8, zoom=6.2, pitch=0)
    layer = _choropleth_layer(gj, zdf)
    tool_tip = {"html": "<b>Zone:</b> {__zone_key__}<br/><b>Total:</b> {metric_total}",
                "style": {"backgroundColor": "white", "color": "black"}}
    r = pdk.Deck(layers=[layer], initial_view_state=view_state, map_style=None, tooltip=tool_tip)
    st.pydeck_chart(r)

# ---------- PORT (non-lobster fallback) ----------
def _ensure_port_coords(df: pd.DataFrame, ports_ref_path: str | Path | None) -> pd.DataFrame:
    """
    Ensures we have 'port_lat' and 'port_lon' columns.
    If not in df, tries to load a reference CSV with columns: port, port_lat, port_lon.
    """
    if ("port_lat" in df.columns) and ("port_lon" in df.columns):
        return df

    if ports_ref_path is None:
        return df  # we'll error later with a helpful message

    ref = pd.read_csv(ports_ref_path)
    # expected columns: port, port_lat, port_lon
    for need in ("port", "port_lat", "port_lon"):
        if need not in ref.columns:
            raise ValueError("ports reference CSV must include columns: port, port_lat, port_lon")

    left = df.copy()
    if "port" not in left.columns:
        return left
    left["port"] = left["port"].astype("string").str.strip()
    ref["port"] = ref["port"].astype("string").str.strip()

    merged = left.merge(ref[["port", "port_lat", "port_lon"]], on="port", how="left")
    return merged

def port_totals(df: pd.DataFrame, metric: str = "value", ports_ref_path: str | Path | None = "data/geo/ports.csv") -> pd.DataFrame:
    if "port" not in df.columns:
        return pd.DataFrame(columns=["port", "metric_total", "port_lat", "port_lon"])

    df2 = _ensure_port_coords(df, ports_ref_path)
    if ("port_lat" not in df2.columns) or ("port_lon" not in df2.columns):
        return pd.DataFrame(columns=["port", "metric_total", "port_lat", "port_lon"])

    gp = (
        df2.dropna(subset=["port"])
           .groupby(["port", "port_lat", "port_lon"], dropna=True)[metric]
           .sum()
           .reset_index()
    )
    gp.columns = ["port", "port_lat", "port_lon", "metric_total"]
    return gp

def render_port_map(df: pd.DataFrame, metric: str = "value", ports_ref_path: str | Path | None = "data/geo/ports.csv"):
    pdf = port_totals(df, metric=metric, ports_ref_path=ports_ref_path)
    if pdf.empty:
        st.info(
            "No port-level map available. Ensure your data has 'port' *and* coordinates "
            "('port_lat','port_lon') or add a reference CSV at data/geo/ports.csv."
        )
        return

    max_val = pdf["metric_total"].max() if not pdf.empty else 1.0
    # scale radius (meters) between 400 and 3000 based on contribution
    def _rad(v): return 400 + 2600 * (v / max_val if max_val > 0 else 0)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=pdf,
        get_position='[port_lon, port_lat]',
        get_radius='metric_total',
        radius_scale=1,  # we pre-scale via column below
        pickable=True,
        get_fill_color=[15, 108, 141, 160],
        get_line_color=[0, 0, 0, 120],
        lineWidthMinPixels=1,
    )

    # Precompute scaled radius column
    pdf = pdf.assign(scaled_radius=pdf["metric_total"].apply(_rad))
    layer.data = pdf
    layer.get_radius = "scaled_radius"

    view_state = pdk.ViewState(latitude=44.2, longitude=-68.8, zoom=6.2, pitch=0)
    tooltip = {"html": "<b>Port:</b> {port}<br/><b>Total:</b> {metric_total:,.0f}",
               "style": {"backgroundColor": "white", "color": "black"}}
    r = pdk.Deck(layers=[layer], initial_view_state=view_state, map_style=None, tooltip=tooltip)
    st.pydeck_chart(r)

# ---------- Public choice ----------
def render_map_auto(df: pd.DataFrame, geojson_path: str | Path, metric: str = "value", is_lobster: bool = False):
    if is_lobster:
        render_zone_map(df, geojson_path, metric=metric)
    else:
        render_port_map(df, metric=metric, ports_ref_path="data/geo/ports.csv")

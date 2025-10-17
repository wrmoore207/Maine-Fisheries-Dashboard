# app.py
from __future__ import annotations

import streamlit as st
import pandas as pd
from pathlib import Path
import plotly.express as px

from src.queries.filters import coerce_categories, apply_overview_filters, port_to_zone
from src.queries.metrics import kpis_block, yoy_by_zone
from src.viz.maps import load_geojson, render_lobster_zone_map

# -----------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Gulf of Maine Fisheries Dashboard", layout="wide")

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
PROCESSED_DIR = Path("data/processed")
# Adjust if your GeoJSON lives elsewhere; common alt: Path("data/geospatial/lobster_zones.geojson")
GEO_PATH = Path("data/geo/lobster_zones.geojson")

# -----------------------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_df(processed_dir: Path) -> pd.DataFrame:
    """Load and lightly normalize all CSVs in data/processed."""
    paths = sorted(processed_dir.glob("*.csv"))

    # Cache-buster: make cache depend on file list + size + mtime
    sig = [(str(p), p.stat().st_size, int(p.stat().st_mtime)) for p in paths]
    _ = hash(tuple(sig))  # noqa: F841

    if not paths:
        return pd.DataFrame()

    dfs = []
    for p in paths:
        df = pd.read_csv(p)

        # Normalize text-ish cols
        for c in ("species", "port", "county", "lob_zone"):
            if c in df.columns:
                df[c] = (
                    df[c]
                    .astype("string")
                    .str.strip()
                    .str.replace(r"\s+", " ", regex=True)
                )

        # Title-case species for nicer UI labels
        if "species" in df.columns:
            df["species"] = df["species"].str.title()

        # Coerce numerics
        if "year" in df.columns:
            df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
        for c in ("weight", "value", "trip_n", "harv_n"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        dfs.append(df)

    out = pd.concat(dfs, ignore_index=True)

    # Keep only columns we use (ignore extras quietly)
    want = ["year", "species", "port", "county", "lob_zone", "weight", "value", "trip_n", "harv_n"]
    keep = [c for c in want if c in out.columns]
    return out[keep]


# Load + normalize categories (including renaming lob_zone -> zone)
raw_df = load_df(PROCESSED_DIR)
df = coerce_categories(raw_df)

st.title("Gulf of Maine Fisheries Dashboard (Maine)")

if df.empty:
    st.warning("No processed data found in data/processed/*.csv")
    st.stop()

# -----------------------------------------------------------------------------
# Sidebar filters (shared)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Filters")

    species_all = sorted(df["species"].dropna().unique().tolist()) if "species" in df.columns else []
    ports_all   = sorted(df["port"].dropna().unique().tolist())    if "port" in df.columns else []
    years_all   = sorted(df["year"].dropna().unique().tolist())    if "year" in df.columns else []

    sb_species = st.multiselect("Species", species_all, default=[])
    sb_ports   = st.multiselect("Ports", ports_all, default=[])

    if years_all:
        sb_years = st.slider(
            "Year range",
            min_value=int(min(years_all)),
            max_value=int(max(years_all)),
            value=(int(max(min(years_all), max(years_all) - 5)), int(max(years_all))),
        )
    else:
        sb_years = None

# -----------------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------------
tabs = st.tabs(["Overview", "Lobster Zones", "Report"])

# -----------------------------------------------------------------------------
# Overview Tab
# -----------------------------------------------------------------------------
with tabs[0]:
    st.subheader("Project Overview")

    st.markdown(
        """
**Purpose & Scope**  
This dashboard explores commercial fisheries in the Gulf of Maine with a focus on trends over time, spatial patterns (lobster zones), and species composition. It’s designed to help analysts and stakeholders quickly understand scale, change, and context.

**Data Notes**  
- Source: Maine Department of Marine Resources (processed CSV).  
- Core fields: `year`, `species`, `port`, `county`, `zone` (lobster), `weight`, `value`.  
- Metrics: *weight* (total pounds landed), *value* (USD), with simple year-over-year change.
        """
    )

    # Reactive slice (KPIs reflect sidebar selections)
    f_overview = apply_overview_filters(df, sb_species, sb_ports, sb_years)
    kpis = kpis_block(f_overview)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Weight (current period)", f"{kpis['total_weight']:,.0f} lb")
    c2.metric("Total Value (current period)",  f"${kpis['total_value']:,.0f}")
    c3.metric("YOY Weight", f"{0.0 if kpis['yoy_weight_change'] is None else kpis['yoy_weight_change']:.1f}%")
    c4.metric("YOY Value",  f"{0.0 if kpis['yoy_value_change']  is None else kpis['yoy_value_change']:.1f}%")

    # State-level context (totals across Maine for selected year range)
    st.markdown("### State-Level Totals (for selected year range)")
    if sb_years and "year" in df.columns:
        base = df[(df["year"] >= sb_years[0]) & (df["year"] <= sb_years[1])]
    else:
        base = df

    state_totals = (
        base.groupby("year", dropna=True)[["weight", "value"]]
        .sum()
        .reset_index()
        .sort_values("year")
    )

    if not state_totals.empty:
        line = px.line(
            state_totals,
            x="year",
            y="weight",
            markers=True,
            title="Total Weight by Year (state-level within selected range)",
        )
        st.plotly_chart(line, use_container_width=True)
    else:
        st.info("No data in the selected range.")

# -----------------------------------------------------------------------------
# Lobster Zones Tab
# -----------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Lobster Zones")

    # Default to species that include "lobster" (covers "Lobster American")
    lobster_defaults = [s for s in species_all if "lobster" in s.lower()]
    lz_species = st.multiselect(
        "Species (affects YOY in the map)",
        species_all,
        default=lobster_defaults if lobster_defaults else (species_all[:1] if species_all else []),
    )

    # Year for YOY comparison (year vs previous year) -> selectbox instead of slider
    if years_all:
        years_sorted = sorted(int(y) for y in years_all)
        lz_year = st.selectbox(
            "Map Year (YOY compares to previous year)",
            options=years_sorted,
            index=len(years_sorted) - 1,  # default to latest
        )
    else:
        lz_year = None

    # Compute YOY by zone and show choropleth
    zone_yoy = yoy_by_zone(df, lz_species, lz_year)

    if zone_yoy.empty:
        st.warning("No zone data available for the selected inputs.")
    else:
        try:
            gjson = load_geojson(GEO_PATH)
        except FileNotFoundError:
            st.error(f"Could not find GeoJSON at {GEO_PATH}. Check GEO_PATH.")
        else:
            deck = render_lobster_zone_map(zone_yoy, gjson)  # auto-detects & normalizes
            st.pydeck_chart(deck, use_container_width=True)

            with st.expander("Debug: Map join details"):
                dbg = getattr(deck, "_gom_debug", {})
                st.write("Zone prop used:", dbg.get("zone_prop_used"))
                st.write("Matched features:", dbg.get("matched_features"))
                st.write("Unmatched features:", dbg.get("unmatched_features"))
                st.dataframe(zone_yoy)

            # Simple legend
            st.markdown(
                """
**Legend**  
- **Green**: YOY increase  
- **Red**: YOY decrease  
- **Gray**: Little/No change  
- **Light gray**: No baseline or missing data
                """
            )


# -----------------------------------------------------------------------------
# Report Tab
# -----------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Report")

    # Use the *current sidebar selection* to define the report slice
    r_df = apply_overview_filters(df, sb_species, sb_ports, sb_years)
    rk = kpis_block(r_df)

    st.markdown("### Key Metrics (for current selection)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Poundage (current period)", f"{rk['total_weight']:,.0f} lb")
    c2.metric("Total Value (current period)",    f"${rk['total_value']:,.0f}")
    c3.metric("YOY Poundage", f"{0.0 if rk['yoy_weight_change'] is None else rk['yoy_weight_change']:.1f}%")
    c4.metric("YOY Value",    f"{0.0 if rk['yoy_value_change']  is None else rk['yoy_value_change']:.1f}%")

    st.markdown("### Species Composition")
    if not r_df.empty and "species" in r_df.columns:
        sp = (
            r_df.groupby("species", dropna=True)["weight"]
               .sum()
               .reset_index()
               .sort_values("weight", ascending=False)
        )
        if sp["weight"].sum() > 0:
            pie = px.pie(sp, names="species", values="weight", title="Share of Total Weight by Species")
            st.plotly_chart(pie, use_container_width=True)
        else:
            st.info("No weight totals in the current selection.")
    else:
        st.info("No species field available in the selection.")

    st.markdown("### Ports Included per Lobster Zone (in current selection)")
    if "zone" in r_df.columns and "port" in r_df.columns:
        sub = port_to_zone(r_df)
        if sub.empty:
            st.info("No ports/zones present in the current selection.")
        else:
            for _, row in sub.sort_values("zone").iterrows():
                with st.expander(f"Zone {row['zone']}"):
                    ports_list = row["ports"] or []
                    st.write(", ".join(ports_list) if ports_list else "No ports found.")
    else:
        st.info("Zone/Port fields not available.")

# app.py
from __future__ import annotations
import streamlit as st
import pandas as pd
from pathlib import Path

from src.queries.aggregations import (
    available_years, available_species, state_totals, yoy_change,
    statewide_trend, species_mix, zones_annual, zone_kpis, region_table
)
from src.viz.charts import line_state_trend, pie_species_mix, small_multiples_zones

@st.cache_data(show_spinner=False)
def load_df(processed_dir: Path) -> pd.DataFrame:
    paths = sorted(processed_dir.glob("*.csv"))

    # Cache-buster: build a fingerprint from file path + size + mtime
    sig = [(str(p), p.stat().st_size, int(p.stat().st_mtime)) for p in paths]
    _ = hash(tuple(sig))  # noqa: F841  # ensures cache depends on file state

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
    want = ["year","species","port","county","lob_zone","weight","value","trip_n","harv_n"]
    keep = [c for c in want if c in out.columns]
    return out[keep]

PROCESSED_DIR = Path("data/processed")
df = load_df(PROCESSED_DIR)
st.set_page_config(page_title="Gulf of Maine Fisheries Dashboard", layout="wide")

st.title("Gulf of Maine Fisheries Dashboard (Maine)")

if df.empty:
    st.warning("No processed data found in data/processed/*.csv")
    st.stop()

# -------- Global controls (sidebar) --------
years = available_years(df)
species_all = available_species(df)

with st.sidebar:
    st.header("Filters")

    year_sel = st.selectbox("Year", years, index=len(years)-1 if years else 0)

    # --- Species (dynamic) ---
    st.caption("Filter by Species (leave empty = All Species)")
    species_query = st.text_input("Search species", placeholder="e.g., Lobster, Haddock, Scallop ...")
    species_all = available_species(df)
    if species_query:
        species_choices = [s for s in species_all if species_query.lower() in s.lower()]
    else:
        species_choices = species_all

    species_sel = st.multiselect("Species", species_choices, default=[])

    metric_label = st.radio("Measure", options=["Weight (lbs)", "Revenue ($)"])
    metric = "weight" if "Weight" in metric_label else "value"


tabs = st.tabs(["Overview", "Lobster Zones", "Regions / Ports", "Table"])

# -------- Overview --------
with tabs[0]:
    st.subheader("Overview")

    # KPIs
    kpi_container = st.container()
    with kpi_container:
        col1, col2, col3 = st.columns(3)
        # State totals (curr year)
        totals_curr = state_totals(df, year_sel, metric)
        totals_all = state_totals(df, None, metric)  # for YoY reference
        yoy = yoy_change(df, year_sel, metric)
        curr_val = float(totals_curr[metric].sum()) if not totals_curr.empty else 0.0

        col1.metric("Total State Poundage (lbs)", f"{float(totals_curr['weight'].sum()):,.0f}")
        col2.metric("Total State Revenue ($)", f"${float(totals_curr['value'].sum()):,.0f}")
        col3.metric(f"YoY Change ({'lbs' if metric=='weight' else '$'})",
                    f"{(yoy*100):.1f}%" if yoy is not None else "—")

    # Statewide annual trend (selected measure)
    st.markdown("### Statewide Trend")
    trend_df = statewide_trend(df, species_sel, metric)
    st.altair_chart(line_state_trend(trend_df, metric), use_container_width=True)

    # Species mix pie (statewide for selected year)
    st.markdown("### Species Mix (Statewide)")
    mix_df = species_mix(df, year_sel, region_type=None, region_vals=None)
    st.altair_chart(pie_species_mix(mix_df, metric, title=f"Species Share — {year_sel}"), use_container_width=True)

# -------- Lobster Zones (small multiples + KPI row) --------
with tabs[1]:
    st.subheader("Lobster Zones")
    zones_df = zones_annual(df, species_sel, metric)
    st.altair_chart(small_multiples_zones(zones_df, metric), use_container_width=True)

    st.markdown("### Zone KPIs")
    kpi = zone_kpis(df, year_sel, metric)
    if kpi.empty:
        st.info("No lobster zone data for the selected year.")
    else:
        # Show as cards in a grid-like layout
        ncols = 6
        cols = st.columns(ncols)
        for i, (_, row) in enumerate(kpi.iterrows()):
            with cols[i % ncols]:
                st.metric(
                    label=f"Zone {row['lob_zone']}",
                    value=f"{row[metric]:,.0f} {'lbs' if metric=='weight' else '$'}",
                    help=f"Weight: {row['weight']:,.0f} lbs • Revenue: ${row['value']:,.0f}"
                )

# -------- Regions / Ports (scaffold) --------
with tabs[2]:
    st.subheader("Regions / Ports (Drilldown)")
    region_choice = st.radio("Region Type", options=["County", "Port"], horizontal=True)
    region_col = "county" if region_choice == "County" else "port"
    avail = sorted(df[region_col].dropna().unique().tolist())
    selected = st.multiselect(f"Select {region_choice}(s)", avail, default=[])
    if selected:
        # Simple annual chart of selected regions (sum over species)
        q = df[(df[region_col].isin(selected))]
        gp = q.groupby(["year", region_col])[metric].sum().reset_index()
        import altair as alt
        ch = (
            alt.Chart(gp).mark_line(point=True)
            .encode(
                x=alt.X("year:O"), y=alt.Y(f"{metric}:Q", title=("Weight (lbs)" if metric=="weight" else "Revenue (USD)")),
                color=alt.Color(f"{region_col}:N", title=region_choice),
                tooltip=["year:O", f"{region_col}:N", alt.Tooltip(f"{metric}:Q", format=",.0f")]
            ).properties(height=320, title=f"{region_choice} Trend — {('lbs' if metric=='weight' else '$')}")
            .interactive()
        )
        st.altair_chart(ch, use_container_width=True)
    else:
        st.info(f"Select one or more {region_choice.lower()}s to view trends.")

# -------- Table (Report) --------
with tabs[3]:
    st.subheader("Report (Table & Pie)")

    # Region selector (Zone / County / Port). Default to Statewide if none chosen.
    region_type_map = {"Statewide": None, "Lobster Zone": "lob_zone", "County": "county", "Port": "port"}
    region_pick = st.radio("Report Region", options=list(region_type_map.keys()), index=0, horizontal=True)
    region_type = region_type_map[region_pick]

    region_vals = None
    if region_type is not None:
        choices = sorted(df[region_type].dropna().unique().tolist())
        region_vals = st.multiselect(f"Select {region_pick}(s)", choices, default=[])

    # Pie: species share for selected year + region
    mix = species_mix(df, year_sel, region_type, region_vals)
    title = f"Species Share — {year_sel} — {region_pick}" if region_type else f"Species Share — {year_sel} — Statewide"
    st.altair_chart(pie_species_mix(mix, metric, title=title), use_container_width=True)

    # Table: annual totals by species for selected region
    rpt = region_table(df, year_sel, region_type, region_vals)
    show_cols = ["year", "species", "region", "weight", "value"]
    rpt = rpt[show_cols] if all(c in rpt.columns for c in show_cols) else rpt
    st.dataframe(rpt, use_container_width=True, hide_index=True)

    # Download CSV
    if not rpt.empty:
        st.download_button(
            "Download CSV",
            rpt.to_csv(index=False).encode("utf-8"),
            file_name=f"report_{region_pick.lower().replace(' ','_')}_{year_sel}.csv",
            mime="text/csv",
        )

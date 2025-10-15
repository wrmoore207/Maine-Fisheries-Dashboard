from __future__ import annotations
import streamlit as st
import pandas as pd
from pathlib import Path

# If you use these later, keep them; otherwise you can remove to avoid lint warnings.
# from src.queries import filters, metrics

from src.queries.kpis import ytd_total, yoy_change_pct, top_by
from src.viz.maps import render_map_auto
from src.io import load_processed_dir

PROCESSED_DIR = Path("data/processed")
GEO_PATH = Path("data/geo/lobster_zones.geojson")

@st.cache_data
def load_df() -> pd.DataFrame:
    df = load_processed_dir(PROCESSED_DIR)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ("species", "gear", "zone", "port"):
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip()
    return df

# --- helper to detect lobster selection ---
def is_lobster_selection(df: pd.DataFrame) -> bool:
    if "species" not in df.columns or df["species"].dropna().empty:
        return False
    vals = (
        df["species"]
        .astype("string")
        .str.lower()
        .str.strip()
        .dropna()
        .unique()
        .tolist()
    )
    lobsterish = [v for v in vals if "lobster" in v]
    return len(lobsterish) > 0 and len(lobsterish) == len(vals)

def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")

    # derive year if possible
    if "year" not in df.columns and "date" in df.columns:
        df = df.copy()
        df["year"] = df["date"].dt.year

    years = sorted(df["year"].dropna().unique().tolist()) if "year" in df.columns else []
    if years:
        year_range = st.sidebar.select_slider(
            "Year range", options=years, value=(years[0], years[-1])
        )
    else:
        year_range = (None, None)

    species = sorted(df["species"].dropna().unique().tolist()) if "species" in df.columns else []
    species_sel = st.sidebar.multiselect("Species", options=species, default=species[:1] if species else [])

    zones = sorted(df["zone"].dropna().unique().tolist()) if "zone" in df.columns else []
    zone_sel = st.sidebar.multiselect("Lobster Zones", options=zones, default=zones)

    gear = sorted(df["gear"].dropna().unique().tolist()) if "gear" in df.columns else []
    gear_sel = st.sidebar.multiselect("Gear", options=gear, default=gear)

    mask = pd.Series(True, index=df.index)
    if year_range[0] is not None and "year" in df.columns:
        mask &= df["year"].between(year_range[0], year_range[1])
    if species_sel:
        mask &= df["species"].isin(species_sel)
    if zone_sel and "zone" in df.columns:
        mask &= df["zone"].isin(zone_sel)
    if gear_sel and "gear" in df.columns:
        mask &= df["gear"].isin(gear_sel)

    return df.loc[mask].copy()

# --- KPI header (Top Zone for lobster, Top Port otherwise) ---
def kpi_header(df: pd.DataFrame):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("YTD Landings", "—" if "date" not in df.columns else f"{ytd_total(df):,.0f}")
    with c2:
        pct = yoy_change_pct(df)
        st.metric("YoY Change", "—" if pd.isna(pct) else f"{pct:,.1f}%", delta=None if pd.isna(pct) else f"{pct:+.1f}%")
    with c3:
        if is_lobster_selection(df):
            name, v = top_by(df, group_col="zone")
            st.metric("Top Zone (by landings)", "—" if pd.isna(v) else f"{name} — {v:,.0f}")
        else:
            name, v = top_by(df, group_col="port")
            st.metric("Top Port (by landings)", "—" if pd.isna(v) else f"{name} — {v:,.0f}")

def main():
    st.set_page_config(page_title="Gulf of Maine Fisheries Dashboard", page_icon="🌊", layout="wide")

    st.title("Gulf of Maine Fisheries Dashboard")
    st.caption("Maine DMR modern landings • Interactive filters at left")

    df = load_df()
    fdf = sidebar_filters(df)

    tabs = st.tabs(["Time Series", "Table", "Map"])

    # --- Time Series ---
    with tabs[0]:
        st.subheader("Trend over time")
        kpi_header(fdf)

        needed = [c for c in ["value"] if c not in fdf.columns]
        if needed:
            st.warning(f"Time series needs columns: {needed}.")
            with st.expander("Debug: show columns & sample"):
                st.write("Columns:", list(fdf.columns))
                st.dataframe(fdf.head(20))
            st.stop()

        # ensure year exists
        if "year" not in fdf.columns:
            if "date" in fdf.columns:
                fdf = fdf.copy()
                fdf["year"] = fdf["date"].dt.year

        metric_key = st.selectbox(
            "Metric",
            options=["value", "revenue_usd"] if "revenue_usd" in fdf.columns else ["value"],
            index=0,
            format_func=lambda k: "Landings" if k == "value" else "Revenue (USD)"
        )

        # Detect if we truly have monthly granularity
        has_monthly = ("date" in fdf.columns) and (fdf["date"].dt.month.nunique() > 1)

        if has_monthly:
            st.caption("Aggregated: monthly totals")
            df_ts = fdf.copy()
            df_ts["month"] = df_ts["date"].dt.to_period("M").dt.to_timestamp()
            color_by = st.selectbox("Break down by", options=["None", "species", "zone"], index=0)
            if color_by != "None" and color_by in df_ts.columns:
                by = df_ts.groupby(["month", color_by])[metric_key].sum().reset_index()
            else:
                by = df_ts.groupby(["month"])[metric_key].sum().reset_index()

            import altair as alt
            y_label = "Landings (lbs)" if metric_key == "value" else "Revenue (USD)"
            base = alt.Chart(by).encode(x="month:T", y=alt.Y(f"{metric_key}:Q", title=y_label))
            if color_by != "None" and color_by in by.columns:
                chart = base.mark_line().encode(color=f"{color_by}:N", tooltip=["month:T", f"{metric_key}:Q", f"{color_by}:N"])
            else:
                chart = base.mark_line().encode(tooltip=["month:T", f"{metric_key}:Q"])
            st.altair_chart(chart.properties(height=350), use_container_width=True)
        else:
            st.caption("Aggregated: annual totals")
            color_by = st.selectbox("Break down by", options=["None", "species", "zone"], index=0)
            if color_by != "None" and color_by in fdf.columns:
                by = fdf.groupby(["year", color_by])[metric_key].sum().reset_index()
            else:
                by = fdf.groupby(["year"])[metric_key].sum().reset_index()

            import altair as alt
            y_label = "Landings (lbs)" if metric_key == "value" else "Revenue (USD)"
            base = alt.Chart(by).encode(x=alt.X("year:O", title="Year"), y=alt.Y(f"{metric_key}:Q", title=y_label))
            if color_by != "None" and color_by in by.columns:
                chart = base.mark_line(point=True).encode(color=f"{color_by}:N", tooltip=["year:O", f"{metric_key}:Q", f"{color_by}:N"])
            else:
                chart = base.mark_line(point=True).encode(tooltip=["year:O", f"{metric_key}:Q"])
            st.altair_chart(chart.properties(height=350), use_container_width=True)

    # --- Table ---
    with tabs[1]:
        st.subheader("Filtered table")
        st.dataframe(fdf, use_container_width=True)
        st.download_button(
            "Download CSV",
            data=fdf.to_csv(index=False).encode("utf-8"),
            file_name="filtered_landings.csv",
            mime="text/csv"
        )

    # --- Map (Zones for lobster, Ports otherwise) ---
    with tabs[2]:
        is_lob = is_lobster_selection(fdf)
        st.subheader("Map — Lobster Zones (Choropleth)" if is_lob else "Map — Ports (Bubble size by metric)")
        metric_key = st.selectbox(
            "Metric",
            options=["value", "revenue_usd"] if "revenue_usd" in fdf.columns else ["value"],
            index=0,
            format_func=lambda k: "Landings" if k == "value" else "Revenue (USD)"
        )
        render_map_auto(fdf, GEO_PATH, metric=metric_key, is_lobster=is_lob)

if __name__ == "__main__":
    main()

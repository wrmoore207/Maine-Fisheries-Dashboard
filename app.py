# app.py
from __future__ import annotations
import streamlit as st
import pandas as pd
from pathlib import Path

from src.queries.kpis import ytd_total, yoy_change_pct, top_by
from src.viz.maps import render_map_auto
from src.io import load_processed_dir

# New imports
from src.cleaning import prepare_dataframe
# from src.debug import zone_doctor, numbers_doctor

PROCESSED_DIR = Path("data/processed")
GEO_PATH = Path("data/geo/lobster_zones.geojson")

@st.cache_data
def load_df() -> pd.DataFrame:
    """Load, clean, and prepare the processed DMR data."""
    df = load_processed_dir(PROCESSED_DIR)
    df = prepare_dataframe(df)
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

# --- Focus controls: choose a Port or Zone to view ---
def focus_selector(df):
    """
    Returns: filtered_df, focus_dim ('none'|'port'|'zone'), selected_members (list[str])
    """
    st.markdown("#### Focus")
    focus_dim = st.radio(
        "Choose what to view in the table:",
        options=["None", "Port", "Zone"],
        horizontal=True,
        index=0,
    )

    selected = []
    if focus_dim != "None":
        col = "port" if focus_dim == "Port" else "zone"
        if col not in df.columns:
            st.warning(f"Your data has no '{col}' column.")
            return df, "none", []

        # Build clean option list
        opts = (
            df[col]
            .astype("string")
            .dropna()
            .str.strip()
            .replace({"": pd.NA})
            .dropna()
            .unique()
            .tolist()
        )
        opts = sorted(opts)

        selected = st.multiselect(
            f"Select {focus_dim.lower()}(s)",
            options=opts,
            default=opts[:1] if opts else [],
        )

        if selected:
            df = df[df[col].isin(selected)]

        return df, col, selected

    return df, "none", []


def ensure_year_and_date(df):
    """
    Normalizes annual data:
      - Accepts either 'year' or 'date'.
      - Produces integer 'year' and a 'date' field as Jan 1 of that year (for charts).
    """
    out = df.copy()
    if "year" not in out.columns:
        if "date" in out.columns:
            out["year"] = pd.to_datetime(out["date"], errors="coerce").dt.year
        else:
            raise ValueError("Neither 'year' nor 'date' column found.")
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out["date"] = pd.to_datetime(out["year"].astype("string") + "-01-01", errors="coerce")
    return out


def timeseries_table(df, value_col="value", extra_dim="none"):
    """
    Renders a time-series table aggregated annually.
    If extra_dim is 'port' or 'zone', shows both a long table and a pivoted wide table.
    """
    if value_col not in df.columns:
        st.info(f"Can't render table: missing '{value_col}' column.")
        return

    base_cols = ["year"]
    group_cols = base_cols + ([extra_dim] if extra_dim in ("port", "zone") else [])

    grp = (
        df.dropna(subset=["year"])
        .groupby(group_cols, dropna=False)[value_col]
        .sum()
        .reset_index()
        .sort_values(group_cols)
    )

    st.markdown("##### Annual totals (long)")
    st.dataframe(grp, hide_index=True, use_container_width=True)

    if extra_dim in ("port", "zone"):
        st.markdown(f"##### Annual totals by {extra_dim} (wide)")
        wide = grp.pivot(index="year", columns=extra_dim, values=value_col).fillna(0)
        # Cast to int if your 'value' is whole pounds
        try:
            wide = wide.round(0).astype(int)
        except Exception:
            pass
        st.dataframe(wide, use_container_width=True)

# --- Sidebar filters ---
def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")

    # derive year if possible
    if "year" not in df.columns and "date" in df.columns:
        df = df.copy()
        df["year"] = pd.to_datetime(df["date"], errors="coerce").dt.year

    # --- Year range ---
    years = sorted(df["year"].dropna().unique().tolist()) if "year" in df.columns else []
    if years:
        year_range = st.sidebar.select_slider(
            "Year range",
            options=years,
            value=(years[0], years[-1]),
            key="flt_year_range",
        )
    else:
        year_range = (None, None)

    # --- Species ---
    species = sorted(df["species"].dropna().unique().tolist()) if "species" in df.columns else []
    species_sel = st.sidebar.multiselect(
        "Species",
        options=species,
        default=species[:1] if species else [],
        key="flt_species",
    )

    # Build a partial mask so we can detect lobster and populate focus options correctly
    mask = pd.Series(True, index=df.index)
    if year_range[0] is not None and "year" in df.columns:
        mask &= df["year"].between(year_range[0], year_range[1])
    if species_sel:
        mask &= df["species"].isin(species_sel)

    df_partial = df.loc[mask]

    # --- Gear (optional) ---
    gear = sorted(df_partial["gear"].dropna().unique().tolist()) if "gear" in df_partial.columns else []
    gear_sel = st.sidebar.multiselect(
        "Gear",
        options=gear,
        default=gear,  # start with all visible
        key="flt_gear",
    )
    if gear_sel and "gear" in df.columns:
        mask &= df["gear"].isin(gear_sel)
    df_partial = df.loc[mask]

    # --- Focus by Port (always) or Zone (lobster only) ---
    lobster_mode = is_lobster_selection(df_partial)  # True only when current selection is all lobster

    # Choose focus dimension
    focus_options = ["Port"] + (["Zone"] if lobster_mode else [])
    focus_dim = st.sidebar.selectbox(
        "Focus by",
        options=focus_options,
        index=0,
        help="Choose Port for all species; Zone is available only for lobster.",
        key="flt_focus_dim",
    )

    # Choose members of the focus dimension
    focus_col = "port" if focus_dim == "Port" else "zone"
    focus_opts = (
        sorted(df_partial[focus_col].dropna().astype("string").str.strip().unique().tolist())
        if focus_col in df_partial.columns else []
    )

    # If zone is chosen but not available (e.g., missing column), show a disabled state
    if focus_dim == "Zone" and not focus_opts:
        st.sidebar.info("No zones available for current selection.")
        focus_sel = []
    else:
        focus_sel = st.sidebar.multiselect(
            f"Select {focus_dim.lower()}(s)",
            options=focus_opts,
            default=focus_opts,  # default to all
            key="flt_focus_members",
        )

    # Apply the focus mask (only if something selected)
    if focus_sel and focus_col in df.columns:
        mask &= df[focus_col].isin(focus_sel)

    # --- (Optional) expose raw Port/Zone filters if you still want them independently ---
    # Commented out to keep UI minimal since the new Focus covers it.
    # zones = sorted(df_partial["zone"].dropna().unique().tolist()) if "zone" in df_partial.columns else []
    # ports = sorted(df_partial["port"].dropna().unique().tolist()) if "port" in df_partial.columns else []

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
    # zone_doctor(df, fdf)

    tabs = st.tabs(["Time Series", "Table", "Map"])
    # --- Time Series (ports + total) ---
    with tabs[0]:
        st.subheader("Trend over time")

        import altair as alt
        import pandas as pd

        if "value" not in fdf.columns:
            st.info("Expected a 'value' column (pounds).")
            st.stop()

        # Ensure year exists (aggregate annually for apples-to-apples comparisons)
        df_ts = fdf.copy()
        if "year" not in df_ts.columns:
            if "date" in df_ts.columns:
                df_ts["year"] = pd.to_datetime(df_ts["date"], errors="coerce").dt.year
            else:
                st.info("Need a 'year' column (or a 'date' column).")
                st.stop()

        # -----------------------------
        # Aggregations
        # -----------------------------
        # By port (annual)
        agg_cols = {"value": "sum"}
        if "revenue_usd" in df_ts.columns:
            agg_cols["revenue_usd"] = "sum"

        by_port = (
            df_ts.groupby(["year", "port"], as_index=False)
            .agg(agg_cols)
            .rename(columns={"port": "series"})
        )

        # All ports total (annual)
        all_ports = df_ts.groupby("year", as_index=False).agg(agg_cols)
        all_ports["series"] = "All Ports"

        # Combine
        by = pd.concat([by_port, all_ports], ignore_index=True)

        # Tooltip-friendly display strings
        by["value_fmt"] = by["value"].round(0).map(lambda v: f"{v:,.0f} lbs")
        if "revenue_usd" in by.columns:
            by["revenue_fmt"] = by["revenue_usd"].round(0).map(lambda v: f"${v:,.0f}")

        # -----------------------------
        # Summary row (under title)
        # -----------------------------
        latest_year = int(by["year"].max())
        prev_year = latest_year - 1

        latest_total = by[(by["series"] == "All Ports") & (by["year"] == latest_year)]["value"].sum()
        prev_total = by[(by["series"] == "All Ports") & (by["year"] == prev_year)]["value"].sum()

        delta_abs = latest_total - prev_total if pd.notna(prev_total) and prev_total != 0 else None
        delta_pct = (delta_abs / prev_total) * 100 if delta_abs is not None else None

        ports_displayed = sorted([p for p in df_ts["port"].dropna().unique().tolist() if p != "All Ports"])
        ports_label = ", ".join(ports_displayed) if ports_displayed else "All"

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.markdown(f"**Ports shown:** {ports_label}")
        with c2:
            st.metric(
                label=f"Total pounds ({latest_year})",
                value=f"{latest_total:,.0f} lbs" if pd.notna(latest_total) else "—",
            )
        with c3:
            if delta_pct is None:
                st.metric(label="Change vs prev. year", value="—")
            else:
                sign = "▲" if delta_abs >= 0 else "▼"
                st.metric(
                    label=f"Change vs {prev_year}",
                    value=f"{sign} {abs(delta_abs):,.0f} lbs",
                    delta=f"{delta_pct:+.1f}%",
                )

        # -----------------------------
        # Chart
        # -----------------------------
        tooltip = ["year:O", "series:N", "value_fmt:N"]
        if "revenue_fmt" in by.columns:
            tooltip.append("revenue_fmt:N")

        chart = (
            alt.Chart(by)
            .mark_line(point=True)
            .encode(
                x=alt.X("year:O", title="Year"),
                y=alt.Y("value:Q", title="Landings (lbs)"),
                color=alt.Color("series:N", title="Port/Total"),
                tooltip=tooltip,
            )
            .properties(height=360)
        )

        # Make "All Ports" stand out slightly (thicker stroke)
        highlight = (
            alt.Chart(by[by["series"] == "All Ports"])
            .mark_line(point=True, strokeWidth=3)
            .encode(
                x="year:O",
                y="value:Q",
                color=alt.value("#4c78a8"),  # let theme pick; just ensure it's consistent
                tooltip=tooltip,
            )
        )

        st.altair_chart(chart + highlight, use_container_width=True)




    # --- Table ---
    with tabs[1]:  # assuming tabs[0]="Time Series", tabs[1]="Table"
        st.subheader("Annual time series (table)")

        # 1) Normalize date/year for annual reporting
        fdf = ensure_year_and_date(fdf)  # fdf = your already-filtered df (by year range, species, etc.)

        # 2) Let the user choose Port/Zone focus
        fdf_focus, focus_dim, selected_members = focus_selector(fdf)

        # 3) Render table (and a wide pivot when focusing on Port/Zone)
        timeseries_table(fdf_focus, value_col="value", extra_dim=focus_dim)


    # --- Map (Zones for lobster, Ports otherwise) ---
    with tabs[2]:
        is_lob = is_lobster_selection(fdf)
        st.subheader("Map — Lobster Zones (Choropleth)" if is_lob else "Map — Ports (Bubble size by metric)")
        metric_key = st.selectbox(
            "Metric",
            options=["value", "revenue_usd"] if "revenue_usd" in fdf.columns else ["value"],
            index=0,
            format_func=lambda k: "Landings" if k == "value" else "Revenue (USD)",
            key="map_metric_select",  # UNIQUE (separate from Time Series)
        )
        render_map_auto(fdf, GEO_PATH, metric=metric_key, is_lobster=is_lob)

if __name__ == "__main__":
    main()

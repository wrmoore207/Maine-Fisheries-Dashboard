# app.py
from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st

from src.io import load_processed_dir
from src.cleaning import prepare_dataframe
from src.queries.kpis import ytd_total, yoy_change_pct, top_by
from src.viz.maps import render_map_auto
from src.ui.controls import multiselect_with_all
from src.queries.filters import active_ports, filter_out_zero_ports

# --- Load data ---
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
        df["species"].astype("string").str.lower().str.strip().dropna().unique().tolist()
    )
    lobsterish = [v for v in vals if "lobster" in v]
    return len(lobsterish) > 0 and len(lobsterish) == len(vals)


def focus_selector(df: pd.DataFrame):
    """
    Returns: filtered_df, focus_dim ('none'|'port'|'zone'), selected_members (list[str])
    Note: We do NOT render a second Ports selector here—sidebar control is the source of truth.
    """
    st.markdown("#### Focus")
    focus_dim = st.radio(
        "Choose what to view in the table:",
        options=["None", "Port", "Zone"],
        horizontal=True,
        index=0,
    )

    if focus_dim == "None":
        return df, "none", []

    if focus_dim == "Port":
        # Ports are already filtered by the sidebar control
        return df, "port", []

    # Zone-specific control
    if "zone" not in df.columns:
        st.info("No zones available.")
        return df, "none", []

    opts = (
        df["zone"].astype("string").str.strip().dropna().unique().tolist()
        if "zone" in df.columns
        else []
    )
    opts = sorted(opts)

    selected = st.multiselect("Select zone(s)", options=opts, default=opts if opts else [])
    if selected:
        df = df[df["zone"].isin(selected)]

    return df, "zone", selected


def ensure_year_and_date(df: pd.DataFrame):
    """Normalize to annual: ensures integer 'year' and a Jan-1 'date' for that year."""
    out = df.copy()
    if "year" not in out.columns:
        if "date" in out.columns:
            out["year"] = pd.to_datetime(out["date"], errors="coerce").dt.year
        else:
            raise ValueError("Neither 'year' nor 'date' column found.")
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out["date"] = pd.to_datetime(out["year"].astype("string") + "-01-01", errors="coerce")
    return out


def timeseries_table(df: pd.DataFrame, value_col: str = "value", extra_dim: str = "none"):
    """Annual totals; if extra_dim is 'port' or 'zone', also show a wide pivot."""
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
        try:
            wide = wide.round(0).astype(int)
        except Exception:
            pass
        st.dataframe(wide, use_container_width=True)


# --- Sidebar filters ---
def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")

    # Ensure year exists if date is present
    if "year" not in df.columns and "date" in df.columns:
        df = df.copy()
        df["year"] = pd.to_datetime(df["date"], errors="coerce").dt.year

    # Year range
    years = sorted(df["year"].dropna().unique().tolist()) if "year" in df.columns else []
    year_range = (
        st.sidebar.select_slider(
            "Year range",
            options=years,
            value=(years[0], years[-1]),
            key="flt_year_range",
        )
        if years
        else (None, None)
    )

    # Species
    species = sorted(df["species"].dropna().unique().tolist()) if "species" in df.columns else []
    species_sel = st.sidebar.multiselect(
        "Species",
        options=species,
        default=species[:1] if species else [],
        key="flt_species",
    )

    # Base mask
    mask = pd.Series(True, index=df.index)
    if year_range[0] is not None and "year" in df.columns:
        mask &= df["year"].between(year_range[0], year_range[1])
    if species_sel:
        mask &= df["species"].isin(species_sel)

    df_masked = df.loc[mask].copy()

    # Metric selection for active-port logic (hook this to a UI toggle later if you want)
    metric_col = st.session_state.get("metric_col", "weight")  # or "weight"

    # Remove zero-only ports in the current slice
    df_nonzero = filter_out_zero_ports(df_masked, metric_col=metric_col)

    # --- Ports control (ONLY in sidebar) ---
    with st.sidebar:
        port_options = active_ports(df_nonzero, metric_col=metric_col)
        selected_ports = multiselect_with_all(
            "Ports",
            port_options,
            default=port_options,  # behaves like All Ports by default
            key="ports_filter",
            help=f"Only ports with non-zero {metric_col} in the current selection are shown.",
            all_label="All Ports",  # 👈 ensure the chip reads exactly 'All Ports'
        )

    # Apply chosen ports
    if selected_ports:
        df_nonzero = df_nonzero[
            df_nonzero["port"].astype("string").str.strip().isin(selected_ports)
        ]

    # Persist selection info for downstream charts
    st.session_state["selected_ports"] = selected_ports
    st.session_state["port_options_all"] = port_options
    st.session_state["ports_all"] = (set(selected_ports) == set(port_options))


    # --- Focus by Port/Zone (Zone only shows a selector) ---
    lobster_mode = is_lobster_selection(df_nonzero)
    focus_options = ["Port"] + (["Zone"] if lobster_mode else [])
    focus_dim = st.sidebar.selectbox(
        "Focus by",
        options=focus_options,
        index=0,
        help="Choose Port for all species; Zone is available only for lobster.",
        key="flt_focus_dim",
    )

    if focus_dim == "Zone":
        # Only show this selector for zones
        if "zone" in df_nonzero.columns:
            focus_opts = (
                df_nonzero["zone"]
                .astype("string").str.strip().dropna().unique().tolist()
            )
            focus_opts = sorted(focus_opts)
        else:
            focus_opts = []

        if not focus_opts:
            st.sidebar.info("No zones available for current selection.")
        else:
            focus_sel = st.sidebar.multiselect(
                "Select zone(s)",
                options=focus_opts,
                default=focus_opts,
                key="flt_focus_members",
            )
            if focus_sel:
                df_nonzero = df_nonzero[df_nonzero["zone"].isin(focus_sel)]

    # Final filtered frame
    return df_nonzero


# --- KPI header (Top Zone for lobster, Top Port otherwise) ---
def kpi_header(df: pd.DataFrame):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("YTD Landings", "—" if "date" not in df.columns else f"{ytd_total(df):,.0f}")
    with c2:
        pct = yoy_change_pct(df)
        st.metric(
            "YoY Change",
            "—" if pd.isna(pct) else f"{pct:,.1f}%",
            delta=None if pd.isna(pct) else f"{pct:+.1f}%",
        )
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
        import altair as alt

        WEIGHT_COL = "weight"  # lbs
        REVENUE_COL = "value"  # dollars

        # Guard: need pounds column
        if WEIGHT_COL not in fdf.columns:
            st.info(f"Expected a '{WEIGHT_COL}' column (pounds).")
            st.stop()

        # Ensure numeric
        df_ts = fdf.copy()
        for c in (WEIGHT_COL, REVENUE_COL):
            if c in df_ts.columns:
                df_ts[c] = pd.to_numeric(df_ts[c], errors="coerce")

        # Ensure we have a year column
        if "year" not in df_ts.columns:
            if "date" in df_ts.columns:
                df_ts["year"] = pd.to_datetime(df_ts["date"], errors="coerce").dt.year
            else:
                st.info("Need a 'year' column (or a 'date' column).")
                st.stop()

        # --- Selection context from sidebar ---
        selected_ports = st.session_state.get("selected_ports", [])
        port_options_all = st.session_state.get("port_options_all", selected_ports)
        ports_all = bool(
            st.session_state.get("ports_all", set(selected_ports) == set(port_options_all))
        )

        # --- Aggregations (sum pounds; include revenue for tooltip if present) ---
        agg_cols = {WEIGHT_COL: "sum"}
        if REVENUE_COL in df_ts.columns:
            agg_cols[REVENUE_COL] = "sum"

        # Aggregate of the CURRENT selection (whatever df_ts contains)
        selected_agg = df_ts.groupby("year", as_index=False).agg(agg_cols)

        # Decide the aggregate series label
        if ports_all:
            agg_label = "All Ports"
        elif len(selected_ports) >= 2:
            agg_label = "Selected Ports Aggregate"
        else:
            agg_label = None  # single port -> no extra aggregate line

        # Build plotting frame
        frames = []
        if not ports_all:
            # Show per-port lines when NOT in "All Ports" mode
            by_port = (
                df_ts.groupby(["year", "port"], as_index=False)
                .agg(agg_cols)
                .rename(columns={"port": "series"})
            )
            frames.append(by_port)

        if agg_label is not None:
            sel = selected_agg.copy()
            sel["series"] = agg_label
            frames.append(sel)

        if not frames:
            # Fallback to per-port
            frames.append(
                df_ts.groupby(["year", "port"], as_index=False)
                .agg(agg_cols)
                .rename(columns={"port": "series"})
            )

        by = pd.concat(frames, ignore_index=True)

        # Tooltip-friendly fields
        by["weight_fmt"] = by[WEIGHT_COL].round(0).map(lambda v: f"{v:,.0f} lbs")
        if REVENUE_COL in by.columns:
            by["revenue_fmt"] = by[REVENUE_COL].round(0).map(lambda v: f"${v:,.0f}")

        # -----------------------------
        # Summary (compute from df_ts so it works for 1 port, many ports, or all)
        # -----------------------------
        latest_year = int(df_ts["year"].max())
        prev_year = latest_year - 1

        latest_total_lbs = df_ts.loc[df_ts["year"] == latest_year, WEIGHT_COL].sum()
        prev_total_lbs = df_ts.loc[df_ts["year"] == prev_year, WEIGHT_COL].sum()

        delta_abs = latest_total_lbs - prev_total_lbs if prev_total_lbs not in (None, 0) else None
        delta_pct = (delta_abs / prev_total_lbs) * 100 if delta_abs is not None else None

        if ports_all:
            ports_label = "All Ports"
        else:
            ports_label = ", ".join(sorted(selected_ports)) if selected_ports else "—"

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.markdown(f"**Ports shown:** {ports_label}")
        with c2:
            st.metric(
                label=f"Total pounds ({latest_year})",
                value=f"{latest_total_lbs:,.0f} lbs"
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
        # Chart (Y = pounds; tooltip shows pounds and revenue if available)
        # -----------------------------
        tooltip = ["year:O", "series:N", "weight_fmt:N"]
        if "revenue_fmt" in by.columns:
            tooltip.append("revenue_fmt:N")

        base = (
            alt.Chart(by)
            .mark_line(point=True)
            .encode(
                x=alt.X("year:O", title="Year"),
                y=alt.Y(f"{WEIGHT_COL}:Q", title="Landings (lbs)"),
                color=alt.Color("series:N", title="Series"),
                tooltip=tooltip,
            )
            .properties(height=360)
        )

        # Emphasize the aggregate line when present (thicker stroke)
        if agg_label:
            highlight = (
                alt.Chart(by[by["series"] == agg_label])
                .mark_line(point=True, strokeWidth=3)
                .encode(x="year:O", y=f"{WEIGHT_COL}:Q", tooltip=tooltip)
            )
            chart = base + highlight
        else:
            chart = base

        st.altair_chart(chart, use_container_width=True)


        # -----------------------------
        # Chart
        # -----------------------------
        tooltip = ["year:O", "series:N", "value_fmt:N"]
        if "revenue_fmt" in by.columns:
            tooltip.append("revenue_fmt:N")

        base = (
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

        # Emphasize the aggregate line when present (thicker stroke)
        if agg_label:
            highlight = (
                alt.Chart(by[by["series"] == agg_label])
                .mark_line(point=True, strokeWidth=3)
                .encode(x="year:O", y="value:Q", tooltip=tooltip)
            )
            chart = base + highlight
        else:
            chart = base

        st.altair_chart(chart, use_container_width=True)

    # --- Table ---
    with tabs[1]:
        st.subheader("Annual time series (table)")
        fdf_norm = ensure_year_and_date(fdf)
        fdf_focus, focus_dim, _ = focus_selector(fdf_norm)
        timeseries_table(fdf_focus, value_col="value", extra_dim=focus_dim)

    # --- Map ---
    with tabs[2]:
        is_lob = is_lobster_selection(fdf)
        st.subheader("Map — Lobster Zones (Choropleth)" if is_lob else "Map — Ports (Bubble size by metric)")
        metric_key = st.selectbox(
            "Metric",
            options=["value", "revenue_usd"] if "revenue_usd" in fdf.columns else ["value"],
            index=0,
            format_func=lambda k: "Landings" if k == "value" else "Revenue (USD)",
            key="map_metric_select",
        )
        render_map_auto(fdf, GEO_PATH, metric=metric_key, is_lobster=is_lob)


if __name__ == "__main__":
    main()
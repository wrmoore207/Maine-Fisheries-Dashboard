# src/debug.py
from __future__ import annotations
import pandas as pd
import streamlit as st
import numpy as np

def zone_doctor(df_raw: pd.DataFrame, df_filtered: pd.DataFrame):
    with st.expander("🩺 Debug: Lobster Zones"):
        c1, c2 = st.columns(2)
        with c1:
            st.caption("Before filters")
            st.write("Columns:", list(df_raw.columns))
            if "zone" in df_raw.columns:
                st.write("Non-null count:", int(df_raw["zone"].notna().sum()))
                st.write("Unique zones:", sorted([v for v in df_raw["zone"].dropna().unique().tolist()]))
            else:
                st.info("No 'zone' column detected in raw data.")

        with c2:
            st.caption("After filters")
            st.write("Columns:", list(df_filtered.columns))
            if "zone" in df_filtered.columns:
                st.write("Non-null count:", int(df_filtered["zone"].notna().sum()))
                st.write("Unique zones:", sorted([v for v in df_filtered["zone"].dropna().unique().tolist()]))
            else:
                st.info("No 'zone' column detected after filters.")

        if "species" in df_filtered.columns and "zone" in df_filtered.columns:
            lob = df_filtered[df_filtered["species"].astype("string").str.contains("lobster", case=False, na=False)]
            st.write("Rows with species ~ 'lobster' and non-null zone:", int(lob["zone"].notna().sum()))
            st.dataframe(lob[lob["zone"].notna()].head(20), use_container_width=True)


def numbers_doctor(df_raw: pd.DataFrame, df_filtered: pd.DataFrame, metric_col: str):
    st.markdown("### 🧪 Numbers Doctor")
    st.caption("Sanity checks to find where totals diverge.")

    if metric_col not in df_filtered.columns:
        st.warning(f"Metric '{metric_col}' not in filtered data.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.write("Rows (raw / filtered)", len(df_raw), "/", len(df_filtered))
    with c2:
        st.write("Metric col:", metric_col)
    with c3:
        if "species" in df_filtered.columns:
            st.write("Species in filtered:",
                     ", ".join(sorted(map(str, df_filtered["species"].dropna().unique())))[:120], "...")

    # 1) Nulls / negatives
    col = pd.to_numeric(df_filtered[metric_col], errors="coerce")
    nulls = int(col.isna().sum())
    negs  = int((col < 0).sum())
    st.write(f"- Null {metric_col} in filtered: **{nulls}**")
    st.write(f"- Negative {metric_col} in filtered: **{negs}**")

    # 2) Unit sanity (if weight_type exists)
    if "weight_type" in df_filtered.columns:
        wt_counts = df_filtered["weight_type"].astype("string").str.lower().value_counts(dropna=False)
        st.write("- weight_type counts:")
        st.dataframe(wt_counts.to_frame("rows"), use_container_width=True)
        st.caption("If not all 'pounds', conversions may be in play (kg/ton → lb).")

    # 3) Year completeness
    if "year" in df_filtered.columns:
        yr_counts = df_filtered.groupby("year", dropna=False)[metric_col].agg(["count","sum"]).reset_index()
        st.write("- Totals by year:")
        st.dataframe(yr_counts, use_container_width=True)

    # 4) Sum reconciliation vs per-zone/per-port
    total_all = float(np.nansum(pd.to_numeric(df_filtered[metric_col], errors="coerce")))

    if "zone" in df_filtered.columns and df_filtered["zone"].notna().any():
        per_zone_sum = (df_filtered.dropna(subset=["zone"])
                        .groupby("zone", dropna=False)[metric_col]
                        .sum(min_count=1)
                        .sum())
        st.write(f"- Overall sum (all rows): **{total_all:,.2f}**")
        st.write(f"- Sum of per-zone totals: **{per_zone_sum:,.2f}**")
        if not np.isclose(total_all, per_zone_sum, rtol=1e-6, atol=0.01):
            st.error("⚠️ Overall total != sum of per-zone totals (null zones or duplicates?).")
            znull = df_filtered[df_filtered["zone"].isna()]
            st.write(f"Rows with NULL zone: {len(znull)}")
            if len(znull) > 0:
                st.dataframe(znull.head(20), use_container_width=True)

    if "port" in df_filtered.columns and df_filtered["port"].notna().any():
        per_port_sum = (df_filtered.dropna(subset=["port"])
                        .groupby("port", dropna=False)[metric_col]
                        .sum(min_count=1)
                        .sum())
        if not np.isclose(total_all, per_port_sum, rtol=1e-6, atol=0.01):
            st.warning("⚠️ Overall total != sum of per-port totals (null ports or duplicates?).")

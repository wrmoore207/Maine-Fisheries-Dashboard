# src/queries/filters.py
from __future__ import annotations
from typing import Iterable, Optional, Tuple
import pandas as pd

# -------- string helpers --------
def _lc(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.lower()

# -------- normalization / coercion --------
def coerce_categories(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize common columns and types.
    - Renames 'lob_zone' -> 'zone'
    - Upper-cases zone values so joins are consistent
    - Strips whitespace on string columns
    - Coerces numerics
    """
    df = df.copy()

    for c in ("species", "port", "county"):
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip()

    # Standardize zone column to "zone"
    if "zone" not in df.columns and "lob_zone" in df.columns:
        df = df.rename(columns={"lob_zone": "zone"})
    if "zone" in df.columns:
        df["zone"] = df["zone"].astype("string").str.strip().str.upper()

    # Year → Int64
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

    # Weight/value numeric
    for num in ("weight", "value", "trip_n", "harv_n"):
        if num in df.columns:
            df[num] = pd.to_numeric(df[num], errors="coerce")

    return df

# -------- simple reusable slicers --------
def apply_overview_filters(
    df: pd.DataFrame,
    species: list[str] | None,
    ports: list[str] | None,
    years: tuple[int, int] | None,
) -> pd.DataFrame:
    """Generic slicer used by Overview to keep KPIs reactive to selections."""
    f = df.copy()
    if species and "species" in f.columns:
        f = f[f["species"].isin(species)]
    if ports and "port" in f.columns:
        f = f[f["port"].isin(ports)]
    if years and "year" in f.columns:
        start, end = years
        f = f[(f["year"] >= start) & (f["year"] <= end)]
    return f

def port_to_zone(f: pd.DataFrame) -> pd.DataFrame:
    """Unique mapping table for legend: zone → [ports]."""
    if "zone" not in f.columns or "port" not in f.columns:
        return pd.DataFrame(columns=["zone", "ports"])
    gp = (
        f.dropna(subset=["zone", "port"])
         .groupby("zone", dropna=True)["port"]
         .unique()
         .reset_index()
    )
    gp["ports"] = gp["port"].apply(lambda a: sorted([p for p in a if isinstance(p, str)]))
    gp = gp.drop(columns=["port"])
    return gp

# -------- your composable filters (safe against missing cols) --------
def filter_df(
    df: pd.DataFrame,
    species: Optional[Iterable[str]] = None,
    year_range: Optional[Tuple[int, int]] = None,
    counties: Optional[Iterable[str]] = None,
    ports: Optional[Iterable[str]] = None,
    lob_zones: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Composable filters for dashboard UI."""
    out = df.copy()

    if species and "species" in out.columns:
        s_lc = set(x.lower() for x in species)
        out = out[_lc(out["species"]).isin(s_lc)]

    if year_range and "year" in out.columns:
        lo, hi = year_range
        out = out[(out["year"] >= lo) & (out["year"] <= hi)]

    if counties and "county" in out.columns:
        c_lc = set(x.lower() for x in counties)
        out = out[_lc(out["county"]).isin(c_lc)]

    if ports and "port" in out.columns:
        p_lc = set(x.lower() for x in ports)
        out = out[_lc(out["port"]).isin(p_lc)]

    # Accept either 'zone' (preferred, already normalized) or legacy 'lob_zone'
    if lob_zones:
        z_lc = set(x.lower() for x in lob_zones)
        if "zone" in out.columns:
            out = out[_lc(out["zone"]).isin(z_lc)]
        elif "lob_zone" in out.columns:
            out = out[_lc(out["lob_zone"]).isin(z_lc)]

    return out

def active_ports(df: pd.DataFrame, metric_col: str = "value") -> list[str]:
    """
    Return ports that have ANY non-zero metric across the input (after other filters).
    Treats NaN as 0. Requires columns: ['port', metric_col].
    """
    if "port" not in df.columns or metric_col not in df.columns:
        return []

    g = (
        df[["port", metric_col]]
        .copy()
        .assign(_m=lambda x: x[metric_col].fillna(0))
        .groupby("port", dropna=False)["_m"]
        .sum()
    )

    return (
        g.loc[g != 0]
        .index.astype("string")
        .str.strip()
        .dropna()
        .tolist()
    )

def filter_out_zero_ports(df: pd.DataFrame, metric_col: str = "value") -> pd.DataFrame:
    """
    Keep only ports with any non-zero metric across the (already masked) dataset.
    """
    keep = set(active_ports(df, metric_col=metric_col))
    if not keep or "port" not in df.columns:
        return df.iloc[0:0].copy()
    m = df["port"].astype("string").str.strip().isin(keep)
    return df.loc[m].copy()

__all__ = [
    "coerce_categories",
    "apply_overview_filters",
    "port_to_zone",
    "filter_df",
    "active_ports",
    "filter_out_zero_ports",
]

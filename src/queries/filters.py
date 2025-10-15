from __future__ import annotations
from typing import Iterable, Optional, Tuple
import pandas as pd


def _lc(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.lower()


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

    if species:
        s_lc = set(x.lower() for x in species)
        out = out[_lc(out["species"]).isin(s_lc)]

    if year_range:
        lo, hi = year_range
        out = out[(out["year"] >= lo) & (out["year"] <= hi)]

    if counties:
        c_lc = set(x.lower() for x in counties)
        out = out[_lc(out["county"]).isin(c_lc)]

    if ports:
        p_lc = set(x.lower() for x in ports)
        out = out[_lc(out["port"]).isin(p_lc)]

    if lob_zones:
        z_lc = set(x.lower() for x in lob_zones)
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
        .sum(min_count=1)
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
    if not keep:
        return df.iloc[0:0].copy()
    m = df["port"].astype("string").str.strip().isin(keep)
    return df.loc[m].copy()

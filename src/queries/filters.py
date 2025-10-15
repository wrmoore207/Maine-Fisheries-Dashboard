from __future__ import annotations
import pandas as pd
from typing import Iterable, Optional, Tuple

def _lc(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower()

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
        s_lc = set([x.lower() for x in species])
        out = out[_lc(out["species"]).isin(s_lc)]

    if year_range:
        lo, hi = year_range
        out = out[(out["year"] >= lo) & (out["year"] <= hi)]

    if counties:
        c_lc = set([x.lower() for x in counties])
        out = out[_lc(out["county"]).isin(c_lc)]

    if ports:
        p_lc = set([x.lower() for x in ports])
        out = out[_lc(out["port"]).isin(p_lc)]

    if lob_zones:
        z_lc = set([x.lower() for x in lob_zones])
        out = out[_lc(out["lob_zone"]).isin(z_lc)]

    return out

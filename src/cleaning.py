# src/cleaning.py
from __future__ import annotations
import pandas as pd

def standardize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Rename headers from the raw CSV to what the app expects."""
    rename_map = {
        "lob_zone": "zone",
        "trip_n": "trips_n",
        "harv_n": "harvesters_n",
    }
    return df.rename(columns=rename_map)


def clean_types(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure data types and trim whitespace for string columns."""
    out = df.copy()

    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
    if "year" not in out.columns and "date" in out.columns:
        out["year"] = out["date"].dt.year
    if "year" in out.columns:
        out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")

    for c in ("species", "gear", "zone", "port", "county", "weight_type"):
        if c in out.columns:
            out[c] = out[c].astype("string").str.strip()

    return out


def normalize_zone(df: pd.DataFrame) -> pd.DataFrame:
    """
    Simply ensure zone column is uppercase A–G and stripped.
    No numeric mapping or parsing — assumes lob_zone already stores letters.
    """
    out = df.copy()
    if "zone" in out.columns:
        out["zone"] = out["zone"].astype("string").str.strip().str.upper()
        out.loc[~out["zone"].isin(list("ABCDEFG")), "zone"] = pd.NA
    return out


def normalize_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create explicit metric columns without overwriting originals.
      - landings_lbs: numeric version of weight
      - revenue_usd: numeric version of value
    """
    out = df.copy()

    if "weight" in out.columns:
        out["landings_lbs"] = pd.to_numeric(out["weight"], errors="coerce")

    if "value" in out.columns:
        out["revenue_usd"] = pd.to_numeric(out["value"], errors="coerce")

    return out


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Unified preprocessing pipeline for the dashboard."""
    out = standardize_headers(df)
    out = clean_types(out)
    out = normalize_zone(out)
    out = normalize_metrics(out)
    return out

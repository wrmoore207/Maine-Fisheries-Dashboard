from __future__ import annotations
import pandas as pd

REQUIRED_COLS = [
    "year", "species", "port", "county", "lob_zone", "weight_type",
    "weight", "value", "trip_n", "harv_n",
]

def validate_frame(df: pd.DataFrame) -> None:
    miss = set(REQUIRED_COLS) - set(df.columns)
    if miss:
        raise ValueError(f"Missing expected columns: {sorted(miss)}")

    # Types/coercion assumptions
    for c in ["year", "weight", "value", "trip_n", "harv_n"]:
        # allow NaN but ensure numeric coercion would work
        pd.to_numeric(df[c], errors="raise")

    # Ranges
    years = df["year"].dropna()
    if not years.between(1900, 2100).all():
        bad = df.loc[~df["year"].between(1900, 2100), "year"].unique().tolist()
        raise ValueError(f"Out-of-range years: {bad}")

    for c in ["weight", "value", "trip_n", "harv_n"]:
        if (df[c].dropna() < 0).any():
            raise ValueError(f"Negative values in {c}")

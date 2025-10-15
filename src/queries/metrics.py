from __future__ import annotations
import pandas as pd

def yearly_totals(df: pd.DataFrame, by=("species",)) -> pd.DataFrame:
    """
    Aggregate weight/value by year and optional groupers (e.g., species, county).
    """
    group_cols = ["year", *by] if by else ["year"]
    agg = (
        df.groupby(group_cols, dropna=False)
          .agg(weight=("weight", "sum"),
               value=("value", "sum"),
               trips=("trip_n", "sum"),
               harvesters=("harv_n", "sum"))
          .reset_index()
          .sort_values(group_cols)
    )
    return agg

def latest_year(df: pd.DataFrame) -> int:
    return int(df["year"].dropna().max())

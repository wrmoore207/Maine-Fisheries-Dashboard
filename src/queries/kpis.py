from __future__ import annotations
import pandas as pd

def _latest_years(df: pd.DataFrame) -> tuple[int|None, int|None]:
    if "year" in df.columns:
        years = sorted([int(y) for y in df["year"].dropna().unique()])
    elif "date" in df.columns:
        years = sorted(df["date"].dt.year.dropna().unique().tolist())
    else:
        return None, None
    if len(years) < 1:
        return None, None
    if len(years) == 1:
        return years[-1], None
    return years[-1], years[-2]

def ytd_total(df: pd.DataFrame, value_col: str = "value") -> float:
    if value_col not in df.columns:
        return float("nan")
    # If annual-only, show latest year total
    if "year" in df.columns and ("date" not in df.columns or df["date"].dt.month.nunique() <= 1):
        y_latest, _ = _latest_years(df)
        if y_latest is None:
            return float("nan")
        return float(df.loc[df["year"] == y_latest, value_col].sum())
    # otherwise use current calendar year based on date
    if "date" in df.columns:
        this_year = pd.Timestamp.today().year
        return float(df.loc[df["date"].dt.year == this_year, value_col].sum())
    return float("nan")

def yoy_change_pct(df: pd.DataFrame, value_col: str = "value") -> float:
    if value_col not in df.columns:
        return float("nan")
    y1, y0 = _latest_years(df)
    if y1 is None or y0 is None:
        return float("nan")
    v1 = df.loc[df.get("year", df["date"].dt.year) == y1, value_col].sum()
    v0 = df.loc[df.get("year", df["date"].dt.year) == y0, value_col].sum()
    if v0 == 0:
        return float("nan")
    return float((v1 - v0) / v0 * 100.0)

def top_by(df: pd.DataFrame, group_col: str, value_col: str = "value") -> tuple[str, float]:
    if (group_col not in df.columns) or (value_col not in df.columns):
        return ("—", float("nan"))
    gp = df.dropna(subset=[group_col]).groupby(group_col, dropna=True)[value_col].sum().sort_values(ascending=False)
    if gp.empty:
        return ("—", float("nan"))
    return (str(gp.index[0]), float(gp.iloc[0]))

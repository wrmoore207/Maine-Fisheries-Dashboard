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

def kpis_block(df: pd.DataFrame) -> dict:
    """Return dict of core KPIs for whatever slice is passed in."""
    if df.empty:
        return {
            "total_weight": 0.0,
            "total_value": 0.0,
            "yoy_weight_change": None,
            "yoy_value_change": None,
        }
    # total current period (last available year within slice)
    if "year" in df.columns:
        max_year = int(df["year"].dropna().max())
        cur = df[df["year"] == max_year]
        prev = df[df["year"] == (max_year - 1)]
    else:
        # no year? treat all as current
        cur, prev = df, df.iloc[0:0]

    total_weight = float(cur["weight"].sum()) if "weight" in df.columns else 0.0
    total_value  = float(cur["value"].sum())  if "value"  in df.columns else 0.0

    def pct(cur_sum: float, prev_sum: float) -> float | None:
        if prev_sum == 0:
            return None
        return (cur_sum - prev_sum) / prev_sum * 100.0

    yoy_weight = pct(
        float(cur["weight"].sum()) if "weight" in df.columns else 0.0,
        float(prev["weight"].sum()) if "weight" in df.columns else 0.0,
    )
    yoy_value = pct(
        float(cur["value"].sum()) if "value" in df.columns else 0.0,
        float(prev["value"].sum()) if "value" in df.columns else 0.0,
    )

    return {
        "total_weight": total_weight,
        "total_value": total_value,
        "yoy_weight_change": yoy_weight,
        "yoy_value_change": yoy_value,
    }

def yoy_by_zone(df: pd.DataFrame, species: list[str] | None, year: int | None, zero_band: float = 0.5) -> pd.DataFrame:
    """
    Summarize YOY change by lobster zone for a selected species (or all).
    Returns columns: zone (UPPER), weight_cur, weight_prev, yoy_pct (float or None),
                     category in {'increase','decrease','no_change','no_baseline'},
                     yoy_label (string for tooltip).
    zero_band: +/- % band treated as "no_change" (default 0.5%).
    """
    f = df.copy()
    # Ensure we have a 'zone' column and normalize to UPPER for joins
    if "zone" not in f.columns:
        if "lob_zone" in f.columns:
            f = f.rename(columns={"lob_zone": "zone"})
        else:
            return pd.DataFrame(columns=["zone","weight_cur","weight_prev","yoy_pct","category","yoy_label"])

    f["zone"] = f["zone"].astype("string").str.strip().str.upper()

    if species:
        f = f[f["species"].isin(species)]

    if year is None and "year" in f.columns:
        if f["year"].dropna().empty:
            return pd.DataFrame(columns=["zone","weight_cur","weight_prev","yoy_pct","category","yoy_label"])
        year = int(f["year"].dropna().max())

    # Aggregate current and previous year
    cur = f[f["year"] == year].groupby("zone", dropna=True)["weight"].sum().rename("weight_cur")
    prev = f[f["year"] == (year - 1)].groupby("zone", dropna=True)["weight"].sum().rename("weight_prev")
    out = pd.concat([cur, prev], axis=1).fillna(0.0).reset_index()

    def pct(c, p):
        if p == 0:
            return None
        return (c - p) / p * 100.0

    out["yoy_pct"] = out.apply(lambda r: pct(r["weight_cur"], r["weight_prev"]), axis=1)

    def cat(p):
        if p is None:
            return "no_baseline"
        if abs(p) < zero_band:
            return "no_change"
        return "increase" if p > 0 else "decrease"

    out["category"] = out["yoy_pct"].apply(cat)

    def label(p):
        if p is None:
            return "No baseline"
        sign = "+" if p > 0 else ""
        return f"{sign}{p:.1f}%"

    out["yoy_label"] = out["yoy_pct"].apply(label)
    return out

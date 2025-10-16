# src/queries/aggregations.py
from __future__ import annotations
import pandas as pd

Metric = str  # "weight" or "value"

def available_years(df: pd.DataFrame) -> list[int]:
    years = sorted(pd.to_numeric(df["year"], errors="coerce").dropna().unique().tolist())
    return [int(y) for y in years]

def available_species(df: pd.DataFrame) -> list[str]:
    return sorted(df["species"].dropna().astype("string").str.strip().unique().tolist())

def state_totals(df: pd.DataFrame, year: int | None, metric: Metric) -> pd.DataFrame:
    q = df.copy()
    if year is not None:
        q = q[q["year"] == year]
    gp = q.groupby("year", dropna=True)[["weight", "value"]].sum().reset_index()
    if year is not None:
        gp = gp[gp["year"] == year]
    return gp if not gp.empty else pd.DataFrame(columns=["year", "weight", "value"])

def yoy_change(df: pd.DataFrame, year: int, metric: Metric) -> float | None:
    # expects annual totals already aggregated by year & metric
    annual = df.groupby("year", dropna=True)[metric].sum().sort_index()
    if year not in annual.index or (year - 1) not in annual.index:
        return None
    prev, curr = float(annual.loc[year - 1]), float(annual.loc[year])
    if prev == 0:
        return None
    return (curr - prev) / prev

def filter_species(df: pd.DataFrame, species_sel: list[str]) -> pd.DataFrame:
    if not species_sel:
        return df
    return df[df["species"].isin(species_sel)]

def statewide_trend(df: pd.DataFrame, species_sel: list[str], metric: Metric) -> pd.DataFrame:
    q = filter_species(df, species_sel)
    gp = q.groupby("year", dropna=True)[metric].sum().reset_index()
    return gp.sort_values("year")

def species_mix(df: pd.DataFrame, year: int, region_type: str | None, region_vals: list[str] | None) -> pd.DataFrame:
    # region_type in {"lob_zone","county","port", None}; when None, statewide
    q = df[df["year"] == year].copy()
    if region_type and region_vals:
        q = q[q[region_type].isin(region_vals)]
    gp = q.groupby("species", dropna=True)[["weight", "value"]].sum().reset_index()
    return gp.sort_values("weight", ascending=False)

def zones_annual(df: pd.DataFrame, species_sel: list[str], metric: Metric) -> pd.DataFrame:
    q = filter_species(df.dropna(subset=["lob_zone"]), species_sel).copy()
    gp = q.groupby(["lob_zone", "year"], dropna=True)[metric].sum().reset_index()
    return gp.sort_values(["lob_zone", "year"])

def zone_kpis(df: pd.DataFrame, year: int, metric: Metric) -> pd.DataFrame:
    q = df[(df["year"] == year) & df["lob_zone"].notna()].copy()
    gp = q.groupby("lob_zone", dropna=True)[["weight", "value"]].sum().reset_index()
    gp["metric"] = gp[metric]
    return gp.sort_values("metric", ascending=False)

def region_table(df: pd.DataFrame, year: int, region_type: str | None, region_vals: list[str] | None) -> pd.DataFrame:
    q = df[df["year"] == year].copy()
    if region_type and region_vals:
        q = q[q[region_type].isin(region_vals)]
    gp = q.groupby(["year", "species"], dropna=True)[["weight", "value"]].sum().reset_index()
    # Add a "region" display column for clarity
    region_label = "Statewide" if not region_type else f"{region_type}"
    gp.insert(2, "region", region_label)
    return gp

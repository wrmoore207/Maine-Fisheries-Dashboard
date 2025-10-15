from pathlib import Path
import pandas as pd
from src.io import read_processed_csv
from src.queries import filter_df, yearly_totals, latest_year

def _load_any():
    # pick one processed CSV present in repo
    candidates = [
        "MaineDMR_lobster_american.csv",
        "MaineDMR_clam_soft.csv",
        "MaineDMR_haddock.csv",
    ]
    for name in candidates:
        p = Path("data/processed") / name
        if p.exists():
            return read_processed_csv(name)
    raise RuntimeError("No processed CSV found for tests.")

def test_filters_and_metrics():
    df = _load_any()
    ly = latest_year(df)
    sub = filter_df(df, year_range=(ly-5, ly))
    assert (sub["year"].between(ly-5, ly)).all()
    agg = yearly_totals(sub, by=("species",))
    assert {"year", "species", "weight", "value", "trips", "harvesters"} <= set(agg.columns)
    # Aggregation should reduce rows vs raw
    assert len(agg) <= len(sub)

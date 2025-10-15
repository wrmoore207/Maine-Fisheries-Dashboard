from __future__ import annotations
from pathlib import Path
import pandas as pd
from .config import PROC_DIR, REQUIRED_COLS

def read_processed_csv(name: str) -> pd.DataFrame:
    """
    Read a processed subset like 'MaineDMR_lobster_american.csv'.
    """
    path = (PROC_DIR / name)
    if not path.exists():
        raise FileNotFoundError(f"Processed file not found: {path}")
    df = pd.read_csv(path)
    # Light schema sanity
    miss = set(REQUIRED_COLS) - set(df.columns)
    if miss:
        raise ValueError(f"{name} missing columns: {sorted(miss)}")
    return df

def list_processed() -> list[Path]:
    return sorted(PROC_DIR.glob("MaineDMR_*.csv"))

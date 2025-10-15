from __future__ import annotations
from pathlib import Path
import pandas as pd
import itertools

READERS = {
    ".parquet": pd.read_parquet,
    ".feather": pd.read_feather,
    ".csv": pd.read_csv,
}


def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    # exact first, then case-insensitive
    for c in candidates:
        if c in df.columns:
            return c
    lower = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None

def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize column names and types for Maine DMR data files.
    Creates canonical columns:
        date, year, species, gear, zone, port, value, revenue_usd
    Handles datasets that are annual-only or have year/month info.
    """

    def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
        # Find first matching column (case-insensitive)
        for c in candidates:
            if c in df.columns:
                return c
        lower = {c.lower(): c for c in df.columns}
        for c in candidates:
            if c.lower() in lower:
                return lower[c.lower()]
        return None

    # --- DATE / YEAR ---
    date_col = _pick_col(df, ["date", "landing_date", "landed_date", "observation_date"])
    ycol = _pick_col(df, ["year", "Year", "YEAR"])
    mcol = _pick_col(df, ["month", "Month", "MONTH", "month_num", "mo"])
    ym_col = _pick_col(df, ["yyyymm", "YYYYMM"])

    # Start by renaming any existing date column
    if date_col:
        df.rename(columns={date_col: "date"}, inplace=True)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    else:
        # Try to construct a date column
        if ycol and mcol:
            df["date"] = pd.to_datetime(
                dict(year=df[ycol].astype(int), month=df[mcol].astype(int), day=1),
                errors="coerce",
            )
        elif ym_col:
            s = df[ym_col].astype(str).str.replace(r"[^0-9]", "", regex=True)
            df["date"] = pd.to_datetime(
                s.str.slice(0, 4) + "-" + s.str.slice(4, 6) + "-01",
                errors="coerce",
            )
        elif ycol:
            # ✅ Annual-only data — construct Jan 1 of each year
            df["year"] = df[ycol].astype(int)
            df["date"] = pd.to_datetime(df["year"].astype(str) + "-01-01", errors="coerce")

    # Ensure a `year` column always exists
    if "year" not in df.columns and "date" in df.columns:
        df["year"] = df["date"].dt.year

    # --- SPECIES ---
    sp = _pick_col(df, ["species", "Species", "species_name", "species_group", "common_name"])
    if sp and sp != "species":
        df.rename(columns={sp: "species"}, inplace=True)

    # --- GEAR ---
    gr = _pick_col(df, ["gear", "Gear", "gear_type"])
    if gr and gr != "gear":
        df.rename(columns={gr: "gear"}, inplace=True)

    # --- ZONE ---
    zn = _pick_col(df, ["zone", "Zone", "ZONE", "lobster_zone"])
    if zn and zn != "zone":
        df.rename(columns={zn: "zone"}, inplace=True)
    if "zone" in df.columns:
        df["zone"] = df["zone"].astype("string").str.strip()

    # --- PORT ---
    pt = _pick_col(df, ["port", "Port", "landing_port", "port_name"])
    if pt and pt != "port":
        df.rename(columns={pt: "port"}, inplace=True)
    if "port" in df.columns:
        df["port"] = df["port"].astype("string").str.strip()

    # --- VALUE (landed weight) ---
    val = _pick_col(
        df,
        [
            "value",
            "landings",
            "landed_weight_lbs",
            "pounds",
            "lbs",
            "weight_lbs",
            "landed_weight",
            "landings_lbs",
            "quantity",
            "landed_pounds",
        ],
    )
    if val and val != "value":
        df.rename(columns={val: "value"}, inplace=True)

    # --- REVENUE (USD) ---
    rev = _pick_col(
        df,
        [
            "revenue_usd",
            "dockside_value",
            "ex_vessel_value",
            "exvessel_value",
            "value_usd",
            "revenue",
            "dollars",
        ],
    )
    if rev and rev != "revenue_usd":
        df.rename(columns={rev: "revenue_usd"}, inplace=True)

    # --- Final cleaning ---
    if "species" in df.columns:
        df["species"] = df["species"].astype("string").str.strip()
    if "gear" in df.columns:
        df["gear"] = df["gear"].astype("string").str.strip()

    return df



def load_processed_dir(base_dir: str | Path = "data/processed") -> pd.DataFrame:
    """
    Auto-discovers processed files (prioritizes parquet, then feather, then csv),
    merges them, and harmonizes columns. Filters to MaineDMR_* by default.
    """
    base = Path(base_dir)
    if not base.exists():
        raise FileNotFoundError(f"Processed folder not found: {base.resolve()}")

    # find files; prefer parquet > feather > csv
    files = []
    for ext in [".parquet", ".feather", ".csv"]:
        files.extend(sorted(base.glob(f"MaineDMR_*{ext}")))
    if not files:
        # if your files don’t start with MaineDMR_, fall back to any file
        for ext in [".parquet", ".feather", ".csv"]:
            files.extend(sorted(base.glob(f"*{ext}")))

    if not files:
        raise FileNotFoundError(
            "No processed data files found in data/processed/. "
            "Expected something like MaineDMR_lobster.parquet or .csv"
        )

    dfs = []
    for f in files:
        reader = READERS.get(f.suffix.lower())
        if not reader:
            continue
        df = reader(f)
        df = _standardize(df)
        df["source_file"] = f.name
        dfs.append(df)

    if not dfs:
        raise FileNotFoundError("Found files, but none could be read. Check formats and dependencies (e.g., pyarrow).")

    # align columns across different sources
    all_cols = sorted(set(itertools.chain.from_iterable(d.columns for d in dfs)))
    dfs = [d.reindex(columns=all_cols) for d in dfs]

    combined = pd.concat(dfs, ignore_index=True)
    return combined


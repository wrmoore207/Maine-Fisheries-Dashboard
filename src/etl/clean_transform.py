# src/etl/clean_transform.py
"""
ETL for Maine DMR modern landings data.

Usage:
  python -m src.etl.clean_transform \
    --input data/raw/MaineDMR_Modern_Landings_Data.csv \
    --outdir data/processed

Optional:
  --species "Lobster American" "Clam Soft"
"""

from __future__ import annotations
import argparse
import logging
from pathlib import Path
from typing import List

import pandas as pd 

# Default species for POC
DEFAULT_SPECIES = ["Lobster American", "Clam Soft", "Haddock"]

# Expected columns in the raw file

REQUIRED_COLS = [
    "year", "species", "port", "county", "lob_zone", "weight_type", 
    "weight", "value", "trip_n", "harv_n"
]

def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level = level,
        format= "%(asctime)s | %(levelname)s | %(message)s",
        datefmt = "%H:%M:%S",
    )
    
def read_raw_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    df = pd.read_csv(path)
    missing = set(REQUIRED_COLS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns: {sorted(missing)}")
    return df

def normalize_types(df: pd.DataFrame) -> pd.DataFrame:
    # Coerce types and standardize known columns. 
    df = df.copy()
    # Numeric coersions (errors="coerce" -> NaN -> later handled)
    for c in ["year", "weight", "value", "trip_n", "harv_n"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # Strip strings
    for c in ["species", "port", "county", "lob_zone", "weight_type"]:
        df[c] = df[c].astype(str).str.strip()
    return df

def validate(df: pd.DataFrame):
    # Light sanity checks; raise on critical issues, log on soft issues
    
    # Year range check
    if not df["year"].dropna().between(1900, 2100).all():
        bad = df.loc[~df["year"].between(1900, 2100), "year"].unique().tolist()
        raise ValueError(f"Found out-of-range years: {bad}")
    
    # Non-negative numeric fields
    for c in ["weight", "value", "trip_n", "harv_n"]:
        if (df[c].dropna() < 0).any():
            raise ValueError (f" Negative values detected in column {c}")
        
    # # Weight type consistency (informational)
    # wtypes = sorted(df[weight_type].dropna().unoique.tolist())
    # loggin.info(f"Detected weight_type values: {wtypes}")
    # # # If you expect pounds only, uncomment to enforce:
    # # if not all(t.lower() == "pounds" for t in wtypes):
    # #     logging.warning("Non-POUNDS weight_type found; verify unit conversions.")
        

def filter_species(df: pd.DataFrame, species_list: List[str]) -> dict[str, pd.DataFrame]:
    """Return a dict of {species_label: subset_df} for the requested species."""
    # Exact-match on canonical labels present in your dataset
    result = {}
    norm = df.copy()
    # Use case-insensitive match to be forgiving
    norm["__species_lc"] = norm["species"].str.lower()
    targets = {s: s.lower() for s in species_list}
    for label, lc in targets.items():
        mask = norm["__species_lc"] == lc
        sub = norm.loc[mask].drop(columns="__species_lc").copy()
        logging.info(f"{label}: {len(sub):,} rows")
        result[label] = sub
    return result

def write_subsets(subsets: dict[str, pd.DataFrame], outdir: Path) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for label, sub in subsets.items():
        # File-friendly name
        fname = f"MaineDMR_{label.lower().replace(' ', '_')}.csv"
        path = outdir / fname
        sub.to_csv(path, index=False)
        logging.info(f"Wrote {label} -> {path} ({len(sub):,} rows)")
        written[label] = path
    return written

def summarize(sub: pd.DataFrame) -> dict:
    if sub.empty:
        return {"rows": 0}
    return {
        "rows": int(len(sub)),
        "years_span": (int(sub["year"].min()), int(sub["year"].max())),
        "total_weight": float(sub["weight"].sum()),
        "total_value": float(sub["value"].sum()),
        "ports": int(sub["port"].nunique()),
        "counties": int(sub["county"].nunique()),
    }
    
def main():
    parser = argparse.ArgumentParser(description="ETL: clean & subset Maine DMR data.")
    parser.add_argument("--input", type=Path, required=True, help="Path to raw master CSV")
    parser.add_argument("--outdir", type=Path, required=True, help="Destination directory for processed CSVs")
    parser.add_argument("--species", nargs="+", default=DEFAULT_SPECIES,
                        help='Species labels to extract (default: "Lobster American" "Clam Soft")')
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    logging.info("Reading raw CSV…")
    df = read_raw_csv(args.input)
    logging.info(f"Raw shape: {df.shape[0]:,} rows × {df.shape[1]} cols")

    logging.info("Normalizing column types…")
    df = normalize_types(df)

    logging.info("Validating dataset…")
    validate(df)

    logging.info(f"Filtering species: {args.species}")
    subsets = filter_species(df, args.species)

    logging.info("Writing subsets…")
    written = write_subsets(subsets, args.outdir)

    # Quick console summaries
    for label, path in written.items():
        summ = summarize(subsets[label])
        logging.info(f"[Summary] {label}: {summ} -> {path}")

if __name__ == "__main__":
    main()
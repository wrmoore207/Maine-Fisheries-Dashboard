# src/etl/clean_transform.py
"""
ETL for Maine DMR modern landings data.

Usage examples:
  # 1) Process ALL species into one master file, plus per-species splits:
  python -m src.etl.clean_transform \
    --input data/raw/MaineDMR_Modern_Landings_Data.csv \
    --outdir data/processed \
    --all --by-species

  # 2) Process only selected species (exact canonical labels in the raw file):
  python -m src.etl.clean_transform \
    --input data/raw/MaineDMR_Modern_Landings_Data.csv \
    --outdir data/processed \
    --species "Lobster American" "Clam Soft" "Haddock"

Notes:
- Master output is always written (filtered or unfiltered), named:
    data/processed/MaineDMR_processed.csv
- When --by-species is used, per-species files are also written:
    data/processed/MaineDMR_<species_snake>.csv
"""

from __future__ import annotations
import argparse
import logging
from pathlib import Path
from typing import Dict, List

import pandas as pd

# Expected columns in the raw file
REQUIRED_COLS = [
    "year", "species", "port", "county", "lob_zone", "weight_type",
    "weight", "value", "trip_n", "harv_n"
]

def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

def read_raw_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    df = pd.read_csv(path)
    missing = set(REQUIRED_COLS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns: {sorted(missing)}")
    return df

# Add near the top of the file
import re

def _safe_slug(name: str) -> str:
    """
    Make a filesystem-safe slug:
    - lowercase
    - replace '&' with 'and'
    - collapse slashes/backslashes to a hyphen
    - replace all other non-alphanumeric with underscores
    - collapse repeated underscores and trim
    - provide a fallback if empty
    """
    if name is None:
        return "species"
    s = str(name).lower().strip()
    s = s.replace("&", "and")
    s = re.sub(r"[\/\\]+", "-", s)           # turn path separators into hyphens
    s = re.sub(r"[^a-z0-9\-]+", "_", s)      # keep a-z, 0-9, and hyphen
    s = re.sub(r"_+", "_", s).strip("_-")    # collapse/trim
    return s or "species"

def normalize_types(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce types and standardize known columns."""
    df = df.copy()

    # Numeric coercions (errors='coerce' -> NaN)
    for c in ["year", "weight", "value", "trip_n", "harv_n"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # String normalization
    for c in ["species", "port", "county", "lob_zone", "weight_type"]:
        df[c] = (
            df[c]
            .astype("string")
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
        )

    # Canonicalize species casing for consistent UI grouping
    if "species" in df.columns:
        df["species"] = df["species"].str.title()

    # Keep lobster zones as-is (A–G expected); just strip/normalize above
    return df

def validate(df: pd.DataFrame):
    """Light sanity checks; raise on critical issues."""
    if not df["year"].dropna().between(1900, 2100).all():
        bad_mask = ~df["year"].between(1900, 2100)
        bad = df.loc[bad_mask, "year"].dropna().unique().tolist()
        raise ValueError(f"Found out-of-range years: {bad}")

    for c in ["weight", "value", "trip_n", "harv_n"]:
        series = df[c].dropna()
        if (series < 0).any():
            raise ValueError(f"Negative values detected in column {c}")

    # Optional informational log for weight_type spread
    try:
        wtypes = sorted(df["weight_type"].dropna().unique().tolist())
        logging.info(f"Detected weight_type values: {wtypes}")
    except Exception:
        pass

def select_species(df: pd.DataFrame, species_list: List[str] | None, select_all: bool) -> pd.DataFrame:
    """Return dataframe filtered to requested species, or all if select_all."""
    if select_all or not species_list:
        return df

    # Case-insensitive exact match
    norm = df.copy()
    norm["__lc"] = norm["species"].str.lower()
    targets = {s.lower() for s in species_list}
    out = norm[norm["__lc"].isin(targets)].drop(columns="__lc")
    missing = [s for s in species_list if s.lower() not in targets.intersection(set(norm["species"].str.lower()))]
    if missing:
        logging.warning(f"Some requested species not found (case-insensitive): {missing}")
    return out

def split_by_species(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Return dict of species -> subset df (exact current casing)."""
    if df.empty:
        return {}
    species_vals = sorted(df["species"].dropna().unique().tolist())
    return {sp: df[df["species"] == sp].copy() for sp in species_vals}

def write_master(df: pd.DataFrame, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "MaineDMR_processed.csv"
    # Reorder columns for consistency
    cols = [c for c in [
        "year", "species", "port", "county", "lob_zone", "weight_type",
        "weight", "value", "trip_n", "harv_n"
    ] if c in df.columns]
    df[cols].to_csv(path, index=False)
    logging.info(f"Wrote master -> {path} ({len(df):,} rows)")
    return path

def write_species_subsets(df: pd.DataFrame, outdir: Path) -> Dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}

    # Track slugs to avoid accidental overwrites if two labels slugify the same
    seen_slugs: set[str] = set()

    for label, sub in split_by_species(df).items():
        base_slug = _safe_slug(label)
        slug = base_slug
        # ensure uniqueness
        i = 2
        while slug in seen_slugs:
            slug = f"{base_slug}_{i}"
            i += 1
        seen_slugs.add(slug)

        fname = f"MaineDMR_{slug}.csv"
        path = outdir / fname
        sub.to_csv(path, index=False)
        logging.info(f"Wrote {label} -> {path} ({len(sub):,} rows)")
        written[label] = path

    return written

def summarize(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"rows": 0}
    return {
        "rows": int(len(df)),
        "years_span": (int(df["year"].min()), int(df["year"].max())) if df["year"].notna().any() else None,
        "total_weight": float(df["weight"].sum()) if "weight" in df.columns else None,
        "total_value": float(df["value"].sum()) if "value" in df.columns else None,
        "ports": int(df["port"].nunique()) if "port" in df.columns else None,
        "counties": int(df["county"].nunique()) if "county" in df.columns else None,
        "species_count": int(df["species"].nunique()) if "species" in df.columns else None,
    }

def main():
    parser = argparse.ArgumentParser(description="ETL: clean & prepare Maine DMR landings data.")
    parser.add_argument("--input", type=Path, required=True, help="Path to raw master CSV")
    parser.add_argument("--outdir", type=Path, required=True, help="Destination directory for processed CSVs")

    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--all", action="store_true", help="Include ALL species")
    grp.add_argument("--species", nargs="+", help="List of species labels to include (exact; case-insensitive). Use '*' for all.")

    parser.add_argument("--by-species", action="store_true", help="Also write one CSV per species")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    logging.info("Reading raw CSV…")
    df = read_raw_csv(args.input)
    logging.info(f"Raw shape: {df.shape[0]:,} rows × {df.shape[1]} cols")

    logging.info("Normalizing column types & casing…")
    df = normalize_types(df)

    logging.info("Validating dataset…")
    validate(df)

    # Determine selection mode
    select_all = bool(args.all) or (args.species and len(args.species) == 1 and args.species[0] == "*")
    chosen = "(ALL species)" if select_all else f"{args.species}"
    logging.info(f"Selecting species: {chosen}")

    df_sel = select_species(df, args.species, select_all=select_all)
    logging.info(f"Selected shape: {df_sel.shape[0]:,} rows")

    if df_sel.empty:
        logging.warning("Selected dataset is empty. Check species labels or selection flags.")

    # Write master file (always)
    master_path = write_master(df_sel, args.outdir)

    # Optionally write per-species splits
    written = {}
    if args.by_species:
        written = write_species_subsets(df_sel, args.outdir)

    # Console summary
    summ = summarize(df_sel)
    logging.info(f"[Summary] Master: {summ} -> {master_path}")
    if args.by_species:
        for label, path in written.items():
            logging.info(f"[Summary] {label}: {summarize(df_sel[df_sel['species'] == label])} -> {path}")

if __name__ == "__main__":
    main()

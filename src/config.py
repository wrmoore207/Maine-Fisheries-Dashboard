from pathlib import Path

# Root-relative data directories
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROC_DIR = DATA_DIR / "processed"
SNAP_DIR = DATA_DIR / "snapshots"

# Canonical species labels used in your CSVs
CANON_SPECIES = ["Lobster American", "Clam Soft", "Haddock"]

# Columns we expect across modern landings (“DMR modern”)
REQUIRED_COLS = [
    "year", "species", "port", "county", "lob_zone", "weight_type",
    "weight", "value", "trip_n", "harv_n",
]

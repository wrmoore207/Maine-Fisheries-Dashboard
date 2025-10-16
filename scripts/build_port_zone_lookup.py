# scripts/build_port_zone_lookup.py
from pathlib import Path
import sys

# --- ensure imports like `from src...` work when run as a script ---
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io import load_processed_dir
from src.queries.port_zone_lookup import (
    build_port_zone_lookup,
    save_port_zone_lookup,
    LOOKUP_PATH,
)

PROCESSED_DIR = ROOT / "data" / "processed"

def main():
    df = load_processed_dir(PROCESSED_DIR)
    lookup = build_port_zone_lookup(df)
    save_port_zone_lookup(lookup)
    print(f"Saved {len(lookup):,} port→zone rows to {LOOKUP_PATH}")
    amb = (lookup["note"] == "AMBIGUOUS").sum()
    if amb:
        print(f"⚠️  {amb} ports are ambiguous — review those rows in {LOOKUP_PATH}.")

if __name__ == "__main__":
    main()

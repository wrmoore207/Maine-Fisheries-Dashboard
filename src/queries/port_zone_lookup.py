from __future__ import annotations
import pandas as pd
from pathlib import Path

DERIVED_DIR = Path("data/derived")
DERIVED_DIR.mkdir(parents=True, exist_ok=True)
LOOKUP_PATH = DERIVED_DIR / "port_zone_lookup.csv"

REQUIRED_COLS = {"port", "lob_zone"}

def build_port_zone_lookup(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"Dataframe missing columns: {sorted(missing)}")

    # only rows where lob_zone already exists
    seed = df.dropna(subset=["port", "lob_zone"]).copy()
    seed["port"] = seed["port"].astype("string").str.strip()
    seed["lob_zone"] = seed["lob_zone"].astype("string").str.strip().str.upper()

    # count occurrences of (port, zone)
    counts = (
        seed.groupby(["port", "lob_zone"], as_index=False)
            .size()
            .rename(columns={"size": "n"})
    )

    # choose the most frequent zone per port
    counts["rank"] = counts.groupby("port")["n"].rank(method="dense", ascending=False)
    winners = counts[counts["rank"] == 1].drop(columns="rank")

    # detect ties (ambiguous mappings)
    ambiguous = (
        counts[counts["rank"] == 1]
        .groupby("port", as_index=False)["lob_zone"]
        .nunique()
    )
    ambiguous_ports = set(ambiguous[ambiguous["lob_zone"] > 1]["port"].tolist())
    winners["note"] = winners["port"].map(lambda p: "AMBIGUOUS" if p in ambiguous_ports else "")

    # keep one row per port (if ambiguous, keep the first by n desc)
    winners = (
        winners.sort_values(["port", "n"], ascending=[True, False])
               .drop_duplicates(subset=["port"], keep="first")
    )

    winners = winners.rename(columns={"lob_zone": "mapped_zone"})
    return winners[["port", "mapped_zone", "n", "note"]].sort_values("port")


def save_port_zone_lookup(lookup: pd.DataFrame, path: Path = LOOKUP_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lookup.to_csv(path, index=False)


def load_port_zone_lookup(path: Path = LOOKUP_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Lookup not found at {path}")
    return pd.read_csv(path, dtype={"port": "string", "mapped_zone": "string"})


def apply_port_zone_lookup(df: pd.DataFrame, lookup: pd.DataFrame, overrides_path: Path | None = DERIVED_DIR / "port_zone_overrides.csv") -> pd.DataFrame:
    out = df.copy()
    out["port"] = out["port"].astype("string").str.strip()

    # base mapping
    out = out.merge(lookup[["port", "mapped_zone"]], on="port", how="left", suffixes=("", "_lk"))

    # manual overrides (if present)
    if overrides_path and overrides_path.exists():
        ov = pd.read_csv(overrides_path, dtype={"port": "string", "mapped_zone": "string"})
        ov["port"] = ov["port"].str.strip()
        out = out.merge(ov[["port", "mapped_zone"]].rename(columns={"mapped_zone": "mapped_zone_override"}), on="port", how="left")
        out["mapped_zone"] = out["mapped_zone_override"].fillna(out["mapped_zone"])
        out = out.drop(columns=["mapped_zone_override"])

    if "lob_zone" not in out.columns:
        out["lob_zone"] = pd.NA
    out["lob_zone"] = out["lob_zone"].fillna(out["mapped_zone"])
    return out.drop(columns=["mapped_zone"])

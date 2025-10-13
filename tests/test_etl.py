from pathlib import Path
import pandas as pd
from src.etl.clean_transform import read_raw_csv, normalize_types, validate, filter_species

def test_species_filter(tmp_path: Path):
    # Tiny synthetic frame
    data = {
        "year": [2020, 2021],
        "species": ["Lobster American", "Clam Soft"],
        "port": ["PORT1", "PORT2"],
        "county": ["COUNTY1", "COUNTY2"],
        "lob_zone": ["A", "B"],
        "weight_type": ["POUNDS", "POUNDS"],
        "weight": [100.0, 50.0],
        "value": [500.0, 200.0],
        "trip_n": [10, 5],
        "harv_n": [2, 1],
    }
    df = pd.DataFrame(data)
    df = normalize_types(df)
    validate(df)
    subs = filter_species(df, ["Lobster American", "Clam Soft"])
    assert len(subs["Lobster American"]) == 1
    assert len(subs["Clam Soft"]) == 1

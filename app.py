import streamlit as st
from pathlib import Path
import pandas as pd
from src.io import list_processed, read_processed_csv
from src.queries import filter_df, yearly_totals, latest_year
from src.viz.maps import lobster_zone_map

st.set_page_config(page_title="Gulf of Maine Fisheries", layout="wide")
st.title("Gulf of Maine Fisheries Dashboard")

files = list_processed()
if not files:
    st.warning("No processed CSVs found in data/processed. Run the ETL first.")
    st.stop()

names = [p.name for p in files]
pick = st.sidebar.selectbox("Dataset", names, index=0)
df = read_processed_csv(pick)

# Sidebar filters
min_y, max_y = int(df["year"].min()), int(df["year"].max())
yr = st.sidebar.slider("Year range", min_y, max_y, (max_y-10, max_y))

species_opts = sorted(df["species"].dropna().unique().tolist())
species = st.sidebar.multiselect("Species", species_opts, default=species_opts)

county_opts = sorted(df["county"].dropna().unique().tolist())
counties = st.sidebar.multiselect("County (optional)", county_opts)

zone_opts = sorted(df["lob_zone"].dropna().unique().tolist())
zones = st.sidebar.multiselect("Lobster Zones (optional)", zone_opts)

fdf = filter_df(df, species=species, year_range=yr, counties=counties, lob_zones=zones)
st.caption(f"{len(fdf):,} rows (latest year in file: {latest_year(df)})")

tab1, tab2, tab3 = st.tabs(["Time Series", "Table", "Map (Lobster Zones)"])

with tab1:
    import plotly.express as px
    agg = yearly_totals(fdf, by=("species",))
    if agg.empty:
        st.info("No data for selected filters.")
    else:
        ts = px.line(agg, x="year", y="weight", color="species", markers=True,
                     title="Total Weight by Year")
        st.plotly_chart(ts, use_container_width=True)
        vs = px.line(agg, x="year", y="value", color="species", markers=True,
                     title="Total Value by Year")
        st.plotly_chart(vs, use_container_width=True)

with tab2:
    st.dataframe(fdf.head(1000))

with tab3:
    st.subheader("Lobster Zones")
    geo_exists = Path("data/geo/lobster_zones.geojson").exists()
    if not geo_exists:
        st.warning("Add GeoJSON at data/geo/lobster_zones.geojson to enable the map.")
    else:
        # Pick a single year to map (default = latest selected)
        y_lo, y_hi = yr
        year_to_map = st.select_slider(
            "Map year",
            options=list(range(min_y, max_y + 1)),
            value=min(y_hi, max_y)
        )
        metric = st.selectbox("Metric", ["weight", "value", "trips", "harvesters"], index=0)
        year_df = fdf[fdf["year"] == year_to_map]
        fig = lobster_zone_map(
            year_df,
            metric=metric,
            geojson_path="data/geo/lobster_zones.geojson",
            title=f"{metric.capitalize()} by Lobster Zone — {year_to_map}"
        )
        if fig is None:
            st.info("No data for this year/filters.")
        else:
            st.plotly_chart(fig, use_container_width=True)



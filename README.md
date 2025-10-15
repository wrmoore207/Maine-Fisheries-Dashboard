# Gulf of Maine Fisheries Dashboard

This repository powers an interactive dashboard exploring Maine DMR modern landings data.
It focuses on multi-species trends over time and by region, beginning with Lobster and Soft-Shell Clams.

## Tech Stack (proposed)
- **App**: Streamlit (Python) for rapid interactive UI
- **Data/ETL**: Python (pandas), optional scheduled jobs for refresh
- **Viz**: Plotly/Altair via Streamlit components
- **Storage**: CSV for demo, PostgreSQL for scale (optional)
- **Deploy**: Streamlit Community Cloud (fast) or Render (more control)

## Getting Started
## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py

```

## Data
- Source: Maine DMR (modern landings)
- Initial subsets included in `/data/`:
  - `MaineDMR_lobster_subset.csv`
  - `MaineDMR_softshell_clam_subset.csv`

## Roadmap
- [ ] Add filters: species, region, year range
- [ ] Time series views (weight/value)
- [ ] Choropleth by coastal region
- [ ] Species comparison view
- [ ] Data dictionary & unit normalization

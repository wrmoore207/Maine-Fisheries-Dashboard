# 🦞 Gulf of Maine Fisheries Dashboard

An interactive **Streamlit dashboard** visualizing fisheries landings data from the **Maine Department of Marine Resources (DMR)**.  
This project explores how landings and revenues vary by **species**, **port**, and **lobster zone** across years — offering insights into economic and ecological shifts in the **Gulf of Maine**.

---

## 🎯 Project Goals
- Provide a **clear, visual overview** of Maine’s commercial fisheries data.  
- Support **species-, port-, and zone-level** filtering and analysis.  
- Enable **data-driven insights** into long-term trends.  
- Demonstrate a **scalable, reproducible pipeline** for fisheries data processing and visualization.  

---

## 🧩 Data Pipeline (ETL)

### **Source**
- **Dataset:** Maine DMR Commercial Landings  
- **Format:** CSV (annual summaries by species, port, county, lobster zone, and weight type)

### **Processing Steps**
Located in [`src/etl/clean_transform.py`](src/etl/clean_transform.py):

1. Normalize column names and data types.  
2. Validate expected schema (`year`, `species`, `port`, `lob_zone`, `weight_type`, etc.).  
3. Standardize weight units (`Live Pounds`, `Meat Pounds`).  
4. Aggregate by species and port, writing processed outputs to:
   - `data/processed/MaineDMR_processed.csv`  
   - `data/processed/by_species/*.csv`

Run the ETL:
```bash
python -m src.etl.clean_transform \
  --input data/raw/MaineDMR_Modern_Landings_Data_2025-10-13.csv \
  --outdir data/processed \
  --all --by-species --verbose

## 📊 Dashboard Features

Built with **Streamlit**, **Pandas**, **Plotly**, and **PyDeck** for visualization.

### **1. Time Series Trends**

- Displays annual totals of `weight` and `revenue_usd`.  
- Supports multi-port selection with:
  - **“All Ports”** → aggregate line.  
  - **“Selected Ports Aggregate”** → total across chosen ports.  
- KPIs show total pounds landed and **year-over-year (YOY) change**.  
- Tooltips clearly differentiate between pounds and dollar values.

### **2. Choropleth Map**

- Visualizes lobster landings by zone using Maine’s official **Lobster Zone GeoJSON** (`data/geo/lobster_zones.geojson`).  
- Interactive hover tooltips display zone name and metric totals.

---

## 🧭 Next Development Steps

- Refine Streamlit layout and KPI presentation for consistency.  
- Add contextual hover tooltips and metadata (e.g., “Source: Maine DMR Landings 2025”).  
- Support combined **Port + Zone** views where applicable.  
- Prepare and publish a **project report** (README + app documentation).  
- Deploy to **Streamlit Cloud** or **Render**.

---

## ⚙️ Tech Stack

| Layer | Tools / Libraries |
|-------|--------------------|
| **App Framework** | [Streamlit](https://streamlit.io/) |
| **Visualization** | [Plotly](https://plotly.com/python/), [PyDeck](https://deckgl.readthedocs.io/en/latest/) |
| **Data Processing** | [Pandas](https://pandas.pydata.org/) |
| **Storage** | CSV (optionally [PostgreSQL](https://www.postgresql.org/)) |
| **Deployment** | [Streamlit Cloud](https://streamlit.io/cloud) or [Render](https://render.com/) |

## 🎨 UI/UX Enhancement Checklist

This section outlines planned improvements to enhance usability, consistency, and overall polish across the Gulf of Maine Fisheries Dashboard.

### **Layout & Structure**
- [ ] Standardize **padding, margins, and spacing** between sections.  
- [ ] Create consistent **tab layout** for Time Series, Map, and Summary views.  
- [ ] Center-align KPI summaries and ensure responsive scaling on all screen sizes.  
- [ ] Refine **sidebar layout** to make filters more intuitive (Port → Zone → Species).  
- [ ] Add clear **titles and subtitles** to charts and map panels.

### **Visual Design**
- [ ] Implement cohesive **color palette** (marine blues, sand neutrals, coral highlights).  
- [ ] Improve **data readability** with larger fonts and balanced white space.  
- [ ] Harmonize **chart color schemes** (consistent between ports, zones, and species).  
- [ ] Add subtle **hover animations** for interactivity and visual feedback.  
- [ ] Include legend and scale indicators where relevant.

### **KPI Presentation**
- [ ] Redesign KPI cards with clear labels and bold numeric emphasis.  
- [ ] Add **YOY arrows or color cues** (green ↑ / red ↓) for quick comparison.  
- [ ] Ensure KPIs dynamically adjust when filtering by Port, Zone, or Species.  
- [ ] Add contextual **tooltips** explaining each metric (e.g., “Total Weight = Sum of Live Pounds per Year”).  

### **Tooltips & Metadata**
- [ ] Include **dataset citation** (e.g., “Source: Maine DMR Landings 2025”).  
- [ ] Add **hover explanations** for weight vs. value metrics.  
- [ ] Include last updated date/time below the dashboard header.  
- [ ] Display metadata for active filters (e.g., *Species: Lobster, Port: All*).

### **User Experience**
- [ ] Add **loading indicators** for charts and maps.  
- [ ] Enable **reset filters** button to quickly return to default state.  
- [ ] Improve mobile responsiveness for small screens.  
- [ ] Streamline **“Create Report”** or **“Export Data”** functionality.  
- [ ] Add optional **dark mode toggle** for low-light environments.

---

**Goal:**  
Refine the dashboard to a professional, data-storytelling standard suitable for public demonstration or stakeholder review.  
Final UI should balance **clarity**, **visual appeal**, and **performance efficiency** across all major views.



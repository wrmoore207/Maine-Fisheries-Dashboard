# src/viz/charts.py
from __future__ import annotations
import altair as alt
import pandas as pd

def format_metric(metric: str) -> str:
    return "Weight (lbs)" if metric == "weight" else "Revenue (USD)"

def line_state_trend(df: pd.DataFrame, metric: str) -> alt.Chart:
    title = f"Statewide Trend — {format_metric(metric)}"
    return (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("year:O", title="Year"),
            y=alt.Y(f"{metric}:Q", title=format_metric(metric)),
            tooltip=["year:O", alt.Tooltip(f"{metric}:Q", title=format_metric(metric), format=",.0f")],
        )
        .properties(height=280, title=title)
        .interactive()
    )

def pie_species_mix(df: pd.DataFrame, metric: str, title: str) -> alt.Chart:
    # Guard empty
    if df.empty:
        return alt.Chart(pd.DataFrame({"note": ["No data"]})).mark_text(size=16).encode(text="note")
    total = df[metric].sum()
    base = df.copy()
    base["share"] = (base[metric] / total) if total else 0
    return (
        alt.Chart(base)
        .mark_arc()
        .encode(
            theta=alt.Theta(f"{metric}:Q"),
            color=alt.Color("species:N", legend=alt.Legend(title="Species")),
            tooltip=[
                "species:N",
                alt.Tooltip(f"{metric}:Q", title=format_metric(metric), format=",.0f"),
                alt.Tooltip("share:Q", title="Share", format=".1%"),
            ],
        )
        .properties(height=280, title=title)
    )

def small_multiples_zones(df: pd.DataFrame, metric: str) -> alt.Chart:
    # expects columns: lob_zone, year, metric
    label = format_metric(metric)
    return (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("year:O", title="Year"),
            y=alt.Y(f"{metric}:Q", title=label),
            facet=alt.Facet("lob_zone:N", columns=3, title="Lobster Zones"),
            tooltip=["lob_zone:N", "year:O", alt.Tooltip(f"{metric}:Q", title=label, format=",.0f")],
        )
        .properties(height=180)
        .interactive()
    )

def pie_species_mix(df: pd.DataFrame, metric: str, title: str, top_n: int = 12) -> alt.Chart:
    import pandas as pd
    if df.empty:
        return alt.Chart(pd.DataFrame({"note": ["No data"]})).mark_text(size=16).encode(text="note")

    # Top N + Other bucketing
    df_sorted = df.sort_values(metric, ascending=False).reset_index(drop=True)
    if len(df_sorted) > top_n:
        head = df_sorted.iloc[:top_n].copy()
        tail_sum = df_sorted.iloc[top_n:][metric].sum()
        other_row = pd.DataFrame({"species": ["Other"], "weight": [0], "value": [0]})
        other_row.loc[0, metric] = tail_sum
        df_plot = pd.concat([head, other_row], ignore_index=True)
    else:
        df_plot = df_sorted

    total = df_plot[metric].sum()
    df_plot["share"] = (df_plot[metric] / total) if total else 0

    return (
        alt.Chart(df_plot)
        .mark_arc()
        .encode(
            theta=alt.Theta(f"{metric}:Q"),
            color=alt.Color("species:N", legend=alt.Legend(title="Species")),
            tooltip=[
                "species:N",
                alt.Tooltip(f"{metric}:Q", title=("Weight (lbs)" if metric == "weight" else "Revenue (USD)"), format=",.0f"),
                alt.Tooltip("share:Q", title="Share", format=".1%"),
            ],
        )
        .properties(height=280, title=title)
    )

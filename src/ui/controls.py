from __future__ import annotations
from typing import Iterable, List
import streamlit as st

def multiselect_with_all(
    label: str,
    options: Iterable[str],
    *,
    default: Iterable[str] | None = None,
    key: str | None = None,
    help: str | None = None,
    all_label: str = "All Ports",   # 👈 allow custom label (capital P)
) -> List[str]:
    """
    Streamlit multiselect that includes an 'All Ports' sentinel chip.
    - If 'All Ports' is selected OR nothing selected, returns the full list.
    - Otherwise returns the explicit selection.
    """
    opts = [str(x) for x in sorted({o.strip() for o in options if isinstance(o, str) and o.strip()})]
    display_opts = [all_label] + opts

    default = list(default) if default else []
    default_is_all = set(default) == set(opts) and len(opts) > 0
    default_display = [all_label] if default_is_all else default

    selected_display = st.multiselect(label, display_opts, default=default_display, key=key, help=help)

    if (all_label in selected_display) or (len(selected_display) == 0):
        return opts
    return [s for s in selected_display if s != all_label]

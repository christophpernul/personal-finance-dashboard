"""Configuration: data location and visual theme.

The data directory can be overridden with the ``FINANCE_DATA_DIR`` environment
variable so the dashboard is portable across machines.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Data location -----------------------------------------------------------
DEFAULT_DATA_DIR = Path(r"D:\SynologyDrive\Finance\data\datahub\target")
DATA_DIR = Path(os.environ.get("FINANCE_DATA_DIR", DEFAULT_DATA_DIR))

EXPENSES_FILE = "target_cashflow__expenses.csv"
INCOMES_FILE = "target_cashflow__incomes.csv"

CSV_SEP = ";"
CSV_DECIMAL = ","
DATE_COLUMN = "date"

# --- Dark theme (matches the existing dashboard look) ------------------------
COLORS = {
    "background": "#2b323b",
    "panel": "#39414c",
    "grid": "#4a5461",
    "text": "#c8ced6",
    "text_muted": "#8b95a1",
    "expense": "#e23b3b",  # red bars
    "income": "#2ec4b6",  # teal/green bars
    "positive": "#2ecc71",  # cashflow surplus
    "negative": "#e74c3c",  # cashflow deficit
    "average": "#29b6f6",  # average reference line (cyan)
    "selected": "#f1c40f",  # highlighted / clicked bar
}

# Consistent color per category is nice-to-have; Plotly's qualitative palette is fine.
CATEGORY_PALETTE = [
    "#e23b3b",
    "#e67e22",
    "#f1c40f",
    "#2ecc71",
    "#1abc9c",
    "#3498db",
    "#9b59b6",
    "#e84393",
    "#fd79a8",
    "#00cec9",
    "#6c5ce7",
    "#0984e3",
    "#a29bfe",
    "#fab1a0",
    "#55efc4",
    "#ffeaa7",
    "#b2bec3",
    "#636e72",
]

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

# Portfolio positions live in the transform layer (one row per position).
DEFAULT_TRANSFORM_DIR = Path(
    r"D:\SynologyDrive\Finance\data\datahub\transform"
)
TRANSFORM_DIR = Path(
    os.environ.get("FINANCE_TRANSFORM_DIR", DEFAULT_TRANSFORM_DIR)
)
PORTFOLIO_FILE = "transform_portfolio__value.csv"

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

# --- Category coloring -------------------------------------------------------
# Categories are grouped into semantic families; every category in a family gets
# a distinct *shade of the same hue*, so related categories (e.g. all
# food & drink) read as one color group while different groups stay visually
# separate. The mapping is fixed, so a category keeps the same color across every
# chart.
import colorsys

# group name -> (base hue color, [member categories in shade order])
CATEGORY_GROUPS: dict[str, tuple[str, list[str]]] = {
    "Food & Drink": (
        "#e23b3b",
        [
            "Restaurants",
            "Fast Food & Sweets",
            "Lebensmittel",
            "Groceries",
            "Alcohol",
            "non Alcoholics",
        ],
    ),
    "Housing": (
        "#3498db",
        [
            "Home",
            "Wohnungseinrichtung",
            "Kaution",
            "Devices",
        ],
    ),
    "Mobility": ("#e67e22", ["Transportation", "Vacation"]),
    "Leisure & Health": (
        "#c99700",
        [  # dark yellow instead of green
            "Sports",
            "Events & Leisure",
            "Clothes & Health",
        ],
    ),
    "Digital": ("#2ecc71", ["Internet", "Apps"]),  # green
    "Giving": ("#e84393", ["Presents", "Present", "Donations"]),
    "Invest & Fees": (
        "#1abc9c",
        [
            "Stocks",
            "Investment",
            "Investment Profit",
            "order_costs",
        ],
    ),
    "Taxes & Fees": ("#8d6e63", ["Steuern & Gebühren", "Taxes & Fees"]),
    "Income": ("#27ae60", ["Salary", "Compensation"]),
    "Other": ("#7f8c8d", ["Other"]),
}

# Fallback hues for any category not listed above (cycled, one hue per new cat).
_FALLBACK_HUES = ["#0984e3", "#6c5ce7", "#00b894", "#fdcb6e", "#d63031"]


def _hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(
        f"{max(0, min(255, round(c * 255))):02x}" for c in rgb
    )


def _shades(base_hex: str, n: int) -> list[str]:
    """Return ``n`` shades of ``base_hex`` from darker to lighter (same hue)."""
    r, g, b = _hex_to_rgb(base_hex)
    hue, _, sat = colorsys.rgb_to_hls(r, g, b)
    # Keep deliberately grey bases grey; only lift saturation for real hues.
    eff_sat = sat if sat < 0.20 else max(sat, 0.45)
    if n <= 1:
        lightnesses = [0.52]
    else:
        lightnesses = [0.40 + 0.30 * i / (n - 1) for i in range(n)]
    return [
        _rgb_to_hex(colorsys.hls_to_rgb(hue, li, eff_sat))
        for li in lightnesses
    ]


def _build_category_colors() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for base_hex, members in CATEGORY_GROUPS.values():
        for cat, color in zip(members, _shades(base_hex, len(members))):
            mapping[cat] = color
    return mapping


CATEGORY_COLORS: dict[str, str] = _build_category_colors()


def category_color(name: str) -> str:
    """Fixed color for a category; unknown categories get a stable fallback hue."""
    if name in CATEGORY_COLORS:
        return CATEGORY_COLORS[name]
    # Deterministic fallback so an unmapped category is still stable across charts.
    idx = abs(hash(name)) % len(_FALLBACK_HUES)
    color = _shades(_FALLBACK_HUES[idx], 1)[0]
    CATEGORY_COLORS[name] = color
    return color

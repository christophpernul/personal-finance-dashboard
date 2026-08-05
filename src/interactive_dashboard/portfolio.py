"""Portfolio positions: loading and aggregation.

The source is ``transform_portfolio__value.csv`` — one row per open position with
its current price/value, the amount invested, and master data (ISIN, symbol,
type, currency). Rows are grouped into ETFs and Stocks via ``security_type``.

Note: the snapshot date can differ per group (e.g. ETFs current, stocks from an
earlier scrape), so the ``as_of`` date is kept and surfaced in the UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config

# Map the raw security_type to a clean, English group label.
GROUP_LABELS = {"ETF": "ETFs", "Aktie": "Stocks"}

# Raw column -> tidy column name.
_RENAME = {
    "date": "as_of",
    "isin": "isin",
    "name": "name",
    "cumulative_shares": "shares",
    "price": "price",
    "value": "value",
    "total_investment": "investment",
    "value_gained": "gain",
    "value_gained_pct": "gain_pct",
    "symbol": "symbol",
    "type": "instrument_type",
    "currency": "currency",
    "security_type": "security_type",
}

# Order of columns shown in the positions table.
DISPLAY_COLUMNS = [
    "group",
    "name",
    "symbol",
    "isin",
    "currency",
    "shares",
    "price",
    "investment",
    "value",
    "gain",
    "gain_pct",
    "as_of",
]


@dataclass
class PortfolioData:
    positions: pd.DataFrame  # one tidy row per position (see _RENAME/DISPLAY_COLUMNS)

    def group_aggregates(self) -> pd.DataFrame:
        """Value/investment/gain totals per group plus an 'All' total row."""
        cols = ["value", "investment", "gain"]
        by_group = self.positions.groupby("group")[cols].sum()
        total = self.positions[cols].sum().to_frame().T
        total.index = ["All"]
        agg = pd.concat([total, by_group])
        agg["gain_pct"] = (
            agg["gain"] / agg["investment"].replace(0, pd.NA)
        ) * 100
        agg["n_positions"] = pd.concat(
            [
                pd.Series({"All": len(self.positions)}),
                self.positions.groupby("group").size(),
            ]
        )
        return agg

    def as_of_by_group(self) -> dict[str, str]:
        """Snapshot date label per group (range if a group mixes dates)."""
        out: dict[str, str] = {}
        for grp, sub in self.positions.groupby("group"):
            dates = sorted(sub["as_of"].dropna().unique())
            if len(dates) == 1:
                out[grp] = pd.Timestamp(dates[0]).strftime("%d %b %Y")
            else:
                out[grp] = (
                    f"{pd.Timestamp(dates[0]):%d %b %Y} – "
                    f"{pd.Timestamp(dates[-1]):%d %b %Y}"
                )
        return out


def load_portfolio_data(path: Path | None = None) -> PortfolioData:
    """Load and tidy the portfolio positions CSV."""
    path = (
        Path(path)
        if path is not None
        else config.TRANSFORM_DIR / config.PORTFOLIO_FILE
    )
    if not path.exists():
        raise FileNotFoundError(
            f"Portfolio data not found: {path}\n"
            f"Set FINANCE_TRANSFORM_DIR or place the CSV there."
        )

    df = pd.read_csv(
        path,
        sep=config.CSV_SEP,
        decimal=config.CSV_DECIMAL,
        parse_dates=["date"],
    )
    df = df.rename(columns=_RENAME)

    numeric = ["shares", "price", "value", "investment", "gain", "gain_pct"]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["group"] = (
        df["security_type"].map(GROUP_LABELS).fillna(df["security_type"])
    )

    df = (
        df[DISPLAY_COLUMNS]
        .sort_values(["group", "value"], ascending=[True, False])
        .reset_index(drop=True)
    )

    return PortfolioData(positions=df)

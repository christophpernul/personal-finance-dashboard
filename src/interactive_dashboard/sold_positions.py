"""Sold positions: loading and aggregation.

Two target tables of the datahub, computed there (the dashboard does no
valuation of its own):

- ``target_portfolio__sold_positions.csv`` — one row per sold (closed) ETF or
  stock position: buy amount, sell proceeds, dividends, order and ongoing
  costs, net profit, return on investment and money-weighted return per year.
  A position that was bought again later is flagged ``rebought``.
- ``target_portfolio__sold_position_flows.csv`` — every cashflow of those
  positions (buys, sells, order costs, dividends, ongoing costs) from the
  investor's view; the flows of a position sum to its net profit.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config
from .portfolio import GROUP_LABELS, _exchange_label
from .returns import xirr

# Order of the groups (cards and table sort).
SOLD_GROUP_ORDER = ["ETFs", "Stocks"]

_MONEY_COLUMNS = [
    "buy_amount",
    "sell_amount",
    "price_gain",
    "dividends",
    "order_costs",
    "ongoing_costs",
    "total_costs",
    "net_profit",
]
_NUMERIC = [
    *_MONEY_COLUMNS,
    "shares_bought",
    "holding_days",
    "roi_pct",
    "annual_return_pct",
]


@dataclass
class SoldPositionsData:
    positions: pd.DataFrame  # one tidy row per sold position
    flows: pd.DataFrame  # [position_id, date, type, amount]

    def group_aggregates(self) -> pd.DataFrame:
        """Money totals, ROI and return per year per group, plus 'All'."""
        rows = {"All": self.positions}
        for grp in SOLD_GROUP_ORDER:
            sub = self.positions[self.positions["group"] == grp]
            if not sub.empty:
                rows[grp] = sub
        return pd.DataFrame(
            {name: self.aggregate(sub) for name, sub in rows.items()}
        ).T

    def aggregate(self, positions: pd.DataFrame) -> pd.Series:
        """Totals of ``positions``: money columns, ROI on the buy amount and
        the money-weighted return per year of all their flows together."""
        totals = positions[_MONEY_COLUMNS].sum()
        invested = totals["buy_amount"]
        totals["roi_pct"] = (
            totals["net_profit"] / invested * 100 if invested else float("nan")
        )
        flows = self.flows[self.flows["position_id"].isin(positions["id"])]
        totals["annual_return_pct"] = (
            xirr(flows["date"], flows["amount"])
            if len(flows)
            else float("nan")
        )
        totals["n_positions"] = len(positions)
        return totals

    def position_flows(self, position_id: str) -> pd.DataFrame:
        flows = self.flows[self.flows["position_id"] == position_id]
        return flows.sort_values("date", kind="stable")


def _read_csv(path: Path, date_cols: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Sold positions data not found: {path}\n"
            f"Set FINANCE_DATA_DIR or run the datahub to create it."
        )
    return pd.read_csv(
        path,
        sep=config.CSV_SEP,
        decimal=config.CSV_DECIMAL,
        parse_dates=date_cols,
    )


def load_sold_positions_data(
    path: Path | None = None, flows_path: Path | None = None
) -> SoldPositionsData:
    """Load and tidy the sold positions and their cashflows."""
    path = Path(path) if path else config.DATA_DIR / config.SOLD_POSITIONS_FILE
    flows_path = (
        Path(flows_path)
        if flows_path
        else config.DATA_DIR / config.SOLD_POSITION_FLOWS_FILE
    )

    df = _read_csv(path, ["open_date", "close_date"])
    for col in _NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["id"] = df["position_id"]  # DataTable row id (for the drill-down)
    df["group"] = (
        df["security_type"].map(GROUP_LABELS).fillna(df["security_type"])
    )
    # Stocks carry no ISIN; the datahub keys them by name instead.
    df["isin"] = df["isin"].where(df["security_type"] != "Aktie", "")
    df["exchange"] = df["depot"].map(_exchange_label)
    df["sold_year"] = df["close_date"].dt.year
    # The CSV stores booleans as text.
    rebought = df["rebought"].astype(str).str.lower() == "true"
    df["rebought"] = rebought.map({True: "Yes", False: "No"})

    rank = {grp: i for i, grp in enumerate(SOLD_GROUP_ORDER)}
    df = (
        df.assign(_rank=df["group"].map(rank).fillna(len(rank)))
        .sort_values(
            ["close_date", "_rank", "name"], ascending=[False, True, True]
        )
        .drop(columns="_rank")
        .reset_index(drop=True)
    )

    flows = _read_csv(flows_path, ["date"])
    flows["amount"] = pd.to_numeric(flows["amount"], errors="coerce")
    return SoldPositionsData(positions=df, flows=flows)

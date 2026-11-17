"""Allocation: how the holdings split by region, distribution, replication and
ETF type, and what they cost.

A *holding* is one open portfolio position (ETFs, stocks, the Riester contract,
crypto; see portfolio.py) or one place cash lies: every cash account with a
positive balance and every running fixed-term deposit (see cash.py; what is
owed on credit cards and loans is left out). Each belongs to one asset class.

Every breakdown shows, per bucket, the number of holdings, their value and the
share of the selected holdings' value, so the buckets of one breakdown always
add up to 100 %. A holding the attribute does not apply to (e.g. the
replication of a stock, the region of a coin) gets a bucket named after its
asset class; one whose master data lacks the value is "Unknown".

Costs:

* *TER* — value-weighted average over the holdings that have one (funds and the
  Riester contract; stocks, crypto and cash have none and are left out).
* *Ongoing costs p.a.* — Σ value × TER: what the holdings cost per year at their
  current value.
* *Costs to date* — order costs and fees paid (the portfolio's ``costs``) plus
  the estimated ongoing costs (TER) since each position was bought.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .cash import CashData
from .portfolio import GROUP_ORDER, PortfolioData, weighted_ter

CASH_CLASS = "Cash"
ASSET_CLASSES = [*GROUP_ORDER, CASH_CLASS]
UNKNOWN = "Unknown"
# Positions worth less than this (EUR) are left out as rounding leftovers.
MIN_HOLDING_VALUE = 1.0


@dataclass(frozen=True)
class Dimension:
    """One breakdown: a raw master-data column and its display buckets."""

    col: str
    title: str
    labels: dict[str, str]  # raw value -> bucket label, in display order
    applies_to: tuple[str, ...]  # asset classes the attribute exists for
    # bucket for a class the attribute doesn't apply to (default: class name)
    other_labels: dict[str, str] | None = None

    def bucket(self, asset_class: str, raw) -> str:
        if asset_class not in self.applies_to:
            return (self.other_labels or {}).get(asset_class, asset_class)
        if pd.isna(raw) or raw == "":
            return UNKNOWN
        return self.labels.get(raw, str(raw).replace("_", " ").title())

    @property
    def order(self) -> list[str]:
        """Bucket labels in display order: the attribute's own values, then
        the unknown ones, then the classes it doesn't apply to."""
        others = [
            (self.other_labels or {}).get(c, c)
            for c in ASSET_CLASSES
            if c not in self.applies_to
        ]
        return [*self.labels.values(), UNKNOWN, *others]


_FUNDS = ("ETFs", "Riester")
DIMENSIONS = [
    Dimension(
        "region",
        "Region",
        {
            "usa": "US",
            "europe": "Europe",
            "emerging": "Emerging Markets",
            "world": "World",
            "commodities": "Commodities",
        },
        applies_to=(*_FUNDS, "Stocks"),
    ),
    Dimension(
        "distribution",
        "Accumulating vs. distributing",
        {"accumulating": "Accumulating", "distributing": "Distributing"},
        applies_to=_FUNDS,
    ),
    Dimension(
        "replication",
        "Physical vs. synthetic",
        {"physical": "Physical", "synthetic": "Synthetic"},
        applies_to=_FUNDS,
    ),
    Dimension(
        "etf_type",
        "Type",
        {
            "index": "Index",
            "dividend": "Dividend",
            "value": "Value",
            "small_cap": "Small Cap",
            "energy": "Energy",
            "real_estate": "Real Estate",
            "commodity": "Commodity",
        },
        applies_to=_FUNDS,
        other_labels={"Stocks": "Single Stocks"},
    ),
]
DIMENSION_BY_COL = {d.col: d for d in DIMENSIONS}

HOLDING_COLUMNS = [
    "asset_class",
    "name",
    "value",
    "ter",
    "cost_pa",
    "costs",
    "ter_cost_to_date",
    *DIMENSION_BY_COL,
]


def _cash_holdings(cash: CashData | None) -> pd.DataFrame:
    if cash is None:
        return pd.DataFrame()
    accounts = cash.accounts[cash.accounts["balance"] > 0]
    deposits = cash.running_deposits
    rows = pd.concat(
        [
            pd.DataFrame(
                {"name": accounts["name"], "value": accounts["balance"]}
            ),
            pd.DataFrame(
                {"name": deposits["name"], "value": deposits["principal"]}
            ),
        ],
        ignore_index=True,
    )
    # Only the columns cash has; the attributes stay empty after the concat.
    return rows.assign(
        asset_class=CASH_CLASS, costs=0.0, ter_cost_to_date=0.0, cost_pa=0.0
    )


def build_holdings(
    portfolio: PortfolioData, cash: CashData | None
) -> pd.DataFrame:
    """Every holding with its asset class, value, costs and the *raw*
    attribute values (see :func:`breakdown` for the buckets)."""
    pos = portfolio.positions.rename(columns={"group": "asset_class"})
    cash_rows = _cash_holdings(cash)
    parts = [pos.reindex(columns=HOLDING_COLUMNS)]
    if not cash_rows.empty:
        parts.append(cash_rows)
    holdings = pd.concat(parts, ignore_index=True).reindex(
        columns=HOLDING_COLUMNS
    )
    for col in ("value", "ter", "cost_pa", "costs", "ter_cost_to_date"):
        holdings[col] = pd.to_numeric(holdings[col], errors="coerce")
    for col in ("cost_pa", "costs", "ter_cost_to_date"):
        holdings[col] = holdings[col].fillna(0.0)
    # Dust (e.g. the rounding leftover of a sold ETF) is no holding.
    return holdings[holdings["value"] >= MIN_HOLDING_VALUE].reset_index(
        drop=True
    )


def select(holdings: pd.DataFrame, classes: list[str] | None) -> pd.DataFrame:
    """Holdings of the given asset classes (all if none are given)."""
    if not classes:
        return holdings
    return holdings[holdings["asset_class"].isin(classes)]


def breakdown(holdings: pd.DataFrame, dimension: Dimension) -> pd.DataFrame:
    """Per bucket: ``n`` holdings, their ``value`` and ``pct`` of the total
    value, in display order; ``names`` lists the holdings (largest first)."""
    cols = ["bucket", "n", "value", "pct", "names"]
    if holdings.empty:
        return pd.DataFrame(columns=cols)
    buckets = [
        dimension.bucket(cls, raw)
        for cls, raw in zip(holdings["asset_class"], holdings[dimension.col])
    ]
    df = holdings.assign(bucket=buckets).sort_values("value", ascending=False)
    out = df.groupby("bucket").agg(
        n=("value", "size"),
        value=("value", "sum"),
        names=("name", lambda s: list(s)),
    )
    total = out["value"].sum()
    out["pct"] = out["value"] / total * 100 if total else 0.0
    rank = {b: i for i, b in enumerate(dimension.order)}
    out = out.reset_index()
    out = out.assign(_rank=out["bucket"].map(rank).fillna(len(rank)))
    return (
        out.sort_values(["_rank", "value"], ascending=[True, False])
        .drop(columns="_rank")
        .reset_index(drop=True)[cols]
    )


@dataclass
class CostSummary:
    value: float
    n_holdings: int
    ter: float  # value-weighted average over the holdings with a TER, %
    ter_value: float  # value of the holdings with a TER
    n_with_ter: int
    cost_pa: float  # Σ value × TER
    costs_paid: float  # order costs and fees paid so far
    ter_cost_to_date: float  # estimated ongoing costs so far

    @property
    def costs_to_date(self) -> float:
        return self.costs_paid + self.ter_cost_to_date

    @property
    def cost_pa_pct(self) -> float:
        """Yearly ongoing costs relative to the whole selection, %."""
        return self.cost_pa / self.value * 100 if self.value else float("nan")


def cost_summary(holdings: pd.DataFrame) -> CostSummary:
    has_ter = holdings["ter"].notna()
    return CostSummary(
        value=float(holdings["value"].sum()),
        n_holdings=len(holdings),
        ter=weighted_ter(holdings["value"], holdings["ter"]),
        ter_value=float(holdings.loc[has_ter, "value"].sum()),
        n_with_ter=int(has_ter.sum()),
        cost_pa=float(holdings["cost_pa"].sum()),
        costs_paid=float(holdings["costs"].sum()),
        ter_cost_to_date=float(holdings["ter_cost_to_date"].sum()),
    )

"""Monthly savings plan: the latest execution of the ETF savings plan.

The datahub writes ``transform_etf__savings_plan.csv``: every ETF bought in
the latest execution (highest ``index`` of the Buys sheet), with the amount
invested, order costs, shares, price and the master-data classification
(``ter``, ``region``, ``distribution``, ``replication``, ``etf_type``).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config
from .portfolio import EXCHANGE_LABELS, weighted_ter

logger = logging.getLogger(__name__)

ATTRIBUTE_COLUMNS = ["region", "distribution", "replication", "etf_type"]


@dataclass
class SavingsPlan:
    buys: pd.DataFrame  # one row per ETF of the latest execution

    @property
    def execution(self) -> int:
        return int(self.buys["index"].max())

    @property
    def amount(self) -> float:
        return float(self.buys["amount"].sum())

    @property
    def costs(self) -> float:
        return float(self.buys["cost"].sum())

    @property
    def ter(self) -> float:
        """Average TER weighted by the amount invested per ETF, %."""
        return weighted_ter(self.buys["amount"], self.buys["ter"])

    @property
    def date_label(self) -> str:
        """Execution date(s), e.g. '2 – 6 Nov 2026'."""
        first, last = self.buys["date"].min(), self.buys["date"].max()
        end = f"{last.day} {last:%b %Y}"
        if first == last:
            return end
        if (first.year, first.month) == (last.year, last.month):
            return f"{first.day} – {end}"
        return f"{first.day} {first:%b %Y} – {end}"

    def as_holdings(self) -> pd.DataFrame:
        """The buys in the shape the allocation breakdowns expect: the amount
        bought is the ``value`` of each ETF."""
        return self.buys.assign(asset_class="ETFs", value=self.buys["amount"])


def load_savings_plan(directory: Path | None = None) -> SavingsPlan | None:
    """Load the latest execution; None if the datahub has not written it yet
    (or it is empty), so the rest of the dashboard still starts."""
    directory = (
        Path(directory) if directory is not None else config.TRANSFORM_DIR
    )
    path = directory / config.SAVINGS_PLAN_FILE
    if not path.exists():
        logger.warning(f"Savings plan not found: {path}")
        return None
    buys = pd.read_csv(
        path,
        sep=config.CSV_SEP,
        decimal=config.CSV_DECIMAL,
        parse_dates=["date"],
    )
    if buys.empty:
        return None
    for col in ("amount", "cost", "shares", "price", "ter"):
        buys[col] = pd.to_numeric(buys[col], errors="coerce")
    buys["cost"] = buys["cost"].fillna(0.0)
    for col in ATTRIBUTE_COLUMNS:
        buys[col] = buys[col].astype("string").str.strip().str.lower()
    buys["depot"] = buys["depot"].map(
        lambda raw: ", ".join(
            EXCHANGE_LABELS.get(p, p.capitalize())
            for p in str(raw).split(", ")
        )
        if isinstance(raw, str)
        else ""
    )
    total = buys["amount"].sum()
    buys["share"] = buys["amount"] / total * 100 if total else 0.0
    return SavingsPlan(buys=buys.sort_values("amount", ascending=False))

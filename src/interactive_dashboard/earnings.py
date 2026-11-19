"""Earnings: dividends and interest received, per year and holding.

The datahub writes ``transform_portfolio__earnings.csv`` with one row per
payment: ``date``, ``kind`` (``dividend`` / ``interest``), ``category``
(``ETF`` / ``Aktie`` for dividends, ``Tagesgeld`` / ``Festgeld`` for interest),
``holding`` (ISIN, stock name or account id), its display ``name`` and the
positive ``amount``.

Every payment belongs to one of four types (``ETF dividends``, ``Stock
dividends``, ``Tagesgeld interest``, ``Festgeld interest``), the stacks of the
yearly bars; each holding keeps a fixed color, a shade of its type's color.
"""
from __future__ import annotations

import colorsys
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config

logger = logging.getLogger(__name__)

KIND_DIVIDEND = "dividend"
KIND_INTEREST = "interest"

# category -> type label; the order is the stacking order (bottom to top)
TYPE_BY_CATEGORY = {
    "ETF": "ETF dividends",
    "Aktie": "Stock dividends",
    "Tagesgeld": "Tagesgeld interest",
    "Festgeld": "Festgeld interest",
}
TYPE_ORDER = list(TYPE_BY_CATEGORY.values())
TYPE_COLORS = {
    "ETF dividends": "#2ec4b6",
    "Stock dividends": "#e67e22",
    "Tagesgeld interest": "#29b6f6",
    "Festgeld interest": "#a78bfa",
}
OTHER_TYPE = "Other"


@dataclass
class EarningsData:
    # one row per payment: date, year, kind, category, type, holding, name,
    # amount
    payments: pd.DataFrame
    holding_colors: dict[str, str]  # holding -> color
    current_year: int

    @property
    def years(self) -> list[int]:
        """Every year from the first payment up to the current one."""
        first = int(self.payments["year"].min())
        return list(range(first, self.current_year + 1))

    def _select(self, kind: str | None) -> pd.DataFrame:
        if kind is None:
            return self.payments
        return self.payments[self.payments["kind"] == kind]

    def yearly_by_type(self) -> pd.DataFrame:
        """year x type of summed amounts (all years, every type)."""
        piv = self.payments.pivot_table(
            index="year",
            columns="type",
            values="amount",
            aggfunc="sum",
            fill_value=0.0,
        )
        types = [t for t in TYPE_ORDER + [OTHER_TYPE] if t in piv.columns]
        return piv.reindex(index=self.years, columns=types, fill_value=0.0)

    def yearly_by_holding(self, kind: str | None = None) -> pd.DataFrame:
        """year x holding of summed amounts; holdings ordered by type, then by
        their all-time amount (largest first)."""
        payments = self._select(kind)
        piv = payments.pivot_table(
            index="year",
            columns="holding",
            values="amount",
            aggfunc="sum",
            fill_value=0.0,
        )
        return piv.reindex(
            index=self.years, columns=self.holding_order(kind), fill_value=0.0
        )

    def holding_order(self, kind: str | None = None) -> list[str]:
        payments = self._select(kind)
        totals = payments.groupby("holding")["amount"].sum()
        type_rank = {t: i for i, t in enumerate(TYPE_ORDER)}
        info = self.holdings().loc[totals.index]
        order = sorted(
            totals.index,
            key=lambda h: (
                type_rank.get(info.at[h, "type"], len(type_rank)),
                -totals[h],
            ),
        )
        return order

    def holdings(self) -> pd.DataFrame:
        """holding -> name, type, category, kind (one row per holding)."""
        return (
            self.payments.sort_values("date")
            .groupby("holding")[["name", "type", "category", "kind"]]
            .last()
        )

    def in_year(
        self,
        year: int,
        kind: str | None = None,
        until: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Amount per holding in ``year`` (optionally only payments up to
        ``until``), largest first: holding, name, type, amount, payments."""
        payments = self._select(kind)
        payments = payments[payments["year"] == year]
        if until is not None:
            payments = payments[payments["date"] <= until]
        grouped = (
            payments.groupby("holding")
            .agg(amount=("amount", "sum"), payments=("amount", "size"))
            .join(self.holdings()[["name", "type"]])
            .reset_index()
        )
        return grouped.sort_values("amount", ascending=False).reset_index(
            drop=True
        )

    def total(
        self,
        year: int | None = None,
        kind: str | None = None,
        until: pd.Timestamp | None = None,
    ) -> float:
        payments = self._select(kind)
        if year is not None:
            payments = payments[payments["year"] == year]
        if until is not None:
            payments = payments[payments["date"] <= until]
        return float(payments["amount"].sum())


def _family(base_hex: str, n: int) -> list[str]:
    """``n`` distinguishable colors around ``base_hex``.

    The hue drifts a little and the lightness is scattered (golden ratio), so
    neighbours in a stack differ while the family still reads as one type. A
    single member keeps the base color."""
    if n <= 1:
        return [base_hex][:n]
    r, g, b = config._hex_to_rgb(base_hex)
    hue, _, sat = colorsys.rgb_to_hls(r, g, b)
    sat = min(max(sat, 0.45), 0.7)
    colors = []
    for i in range(n):
        drift = (i / (n - 1) - 0.5) * 0.12
        light = 0.36 + 0.36 * ((i * 0.618) % 1)
        colors.append(
            config._rgb_to_hex(
                colorsys.hls_to_rgb((hue + drift) % 1, light, sat)
            )
        )
    return colors


def _holding_colors(payments: pd.DataFrame) -> dict[str, str]:
    """A color per holding from its type's family, fixed across all charts."""
    colors: dict[str, str] = {}
    totals = payments.groupby(["type", "holding"])["amount"].sum()
    for type_, group in totals.groupby(level="type"):
        holdings = group.droplevel("type").sort_values(ascending=False).index
        base = TYPE_COLORS.get(type_, "#7f8c8d")
        for holding, color in zip(holdings, _family(base, len(holdings))):
            colors[holding] = color
    return colors


def load_earnings_data(
    directory: Path | None = None, today: pd.Timestamp | None = None
) -> EarningsData | None:
    """Load all dividend and interest payments; None if the datahub has not
    written them yet (or there are none), so the rest of the dashboard still
    starts."""
    directory = (
        Path(directory) if directory is not None else config.TRANSFORM_DIR
    )
    path = directory / config.EARNINGS_FILE
    if not path.exists():
        logger.warning(f"Earnings not found: {path}")
        return None
    payments = pd.read_csv(
        path,
        sep=config.CSV_SEP,
        decimal=config.CSV_DECIMAL,
        parse_dates=["date"],
        dtype={"holding": str, "name": str},
    )
    payments["amount"] = pd.to_numeric(payments["amount"], errors="coerce")
    payments = payments[payments["amount"].notna() & (payments["amount"] != 0)]
    if payments.empty:
        return None
    payments["holding"] = payments["holding"].fillna("").astype(str)
    payments["name"] = payments["name"].fillna(payments["holding"])
    payments["type"] = (
        payments["category"].map(TYPE_BY_CATEGORY).fillna(OTHER_TYPE)
    )
    payments["year"] = payments["date"].dt.year
    today = pd.Timestamp.today() if today is None else pd.Timestamp(today)
    current_year = max(today.year, int(payments["year"].max()))
    return EarningsData(
        payments=payments.sort_values("date").reset_index(drop=True),
        holding_colors=_holding_colors(payments),
        current_year=current_year,
    )

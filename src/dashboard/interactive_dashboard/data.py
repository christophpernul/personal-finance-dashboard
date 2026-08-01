"""Data loading and aggregation.

The source CSVs are already aggregated to one row per month-end, with one column
per category:

* expenses: values are negative (e.g. ``-352,6``)
* incomes:  values are positive

This module normalises both into positive magnitudes and exposes tidy structures
the figure builders can slice by a month range.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config


def _load_csv(path: Path) -> pd.DataFrame:
    """Read one German-locale, semicolon-separated cashflow CSV into a frame
    indexed by month (Timestamp), with numeric category columns."""
    df = pd.read_csv(
        path,
        sep=config.CSV_SEP,
        decimal=config.CSV_DECIMAL,
        parse_dates=[config.DATE_COLUMN],
    )
    df = df.set_index(config.DATE_COLUMN).sort_index()
    # Normalise the monthly index to a period-like month timestamp (month start)
    # so both frames align even if one uses month-end and the other month-start.
    df.index = df.index.to_period("M").to_timestamp()
    df.index.name = "month"
    # Everything except the date is a numeric category column.
    return df.apply(pd.to_numeric, errors="coerce").fillna(0.0)


@dataclass
class FinanceData:
    """In-memory, ready-to-slice view of the cashflow data.

    All amounts are stored as **positive magnitudes** for expenses and income.
    ``net`` keeps its natural sign (income - expenses).
    """

    expense_cats: pd.DataFrame  # month x category, positive magnitudes
    income_cats: pd.DataFrame  # month x category, positive magnitudes
    monthly: pd.DataFrame  # month-indexed: total_expense, total_income, net

    # -- convenience ----------------------------------------------------------
    @property
    def months(self) -> list[pd.Timestamp]:
        return list(self.monthly.index)

    def category_columns(self, kind: str) -> list[str]:
        return list(self._cats(kind).columns)

    def _cats(self, kind: str) -> pd.DataFrame:
        if kind == "expenses":
            return self.expense_cats
        if kind == "income":
            return self.income_cats
        raise ValueError(f"Unknown kind: {kind!r}")

    def totals(self, kind: str) -> pd.Series:
        """Monthly total series (positive) for 'expenses'/'income', or signed
        'net' for 'cashflow'."""
        if kind == "cashflow":
            return self.monthly["net"]
        col = "total_expense" if kind == "expenses" else "total_income"
        return self.monthly[col]

    def slice_months(
        self, start: pd.Timestamp, end: pd.Timestamp
    ) -> "FinanceData":
        """Return a new FinanceData restricted to [start, end] (inclusive)."""
        m = (self.monthly.index >= start) & (self.monthly.index <= end)
        e = (self.expense_cats.index >= start) & (
            self.expense_cats.index <= end
        )
        i = (self.income_cats.index >= start) & (self.income_cats.index <= end)
        return FinanceData(
            expense_cats=self.expense_cats.loc[e],
            income_cats=self.income_cats.loc[i],
            monthly=self.monthly.loc[m],
        )

    def category_breakdown(self, kind: str, month: pd.Timestamp) -> pd.Series:
        """Per-category amounts for a single month, sorted descending, zeros dropped."""
        cats = self._cats(kind)
        if month not in cats.index:
            return pd.Series(dtype=float)
        row = cats.loc[month]
        row = row[row > 0].sort_values(ascending=False)
        return row

    def category_average(self, kind: str) -> pd.Series:
        """Mean monthly amount per category across the (already sliced) months."""
        cats = self._cats(kind)
        if cats.empty:
            return pd.Series(dtype=float)
        avg = cats.mean(axis=0)
        avg = avg[avg > 0].sort_values(ascending=False)
        return avg


def load_finance_data(data_dir: Path | None = None) -> FinanceData:
    """Load and aggregate the cashflow CSVs from ``data_dir``."""
    data_dir = Path(data_dir) if data_dir is not None else config.DATA_DIR
    expenses_path = data_dir / config.EXPENSES_FILE
    incomes_path = data_dir / config.INCOMES_FILE
    for p in (expenses_path, incomes_path):
        if not p.exists():
            raise FileNotFoundError(
                f"Cashflow data not found: {p}\n"
                f"Set FINANCE_DATA_DIR or place the CSVs there."
            )

    raw_expenses = _load_csv(expenses_path)  # negative values
    raw_incomes = _load_csv(incomes_path)  # positive values

    # Positive magnitudes for expenses.
    expense_cats = raw_expenses.abs()
    income_cats = raw_incomes.abs()

    total_expense = expense_cats.sum(axis=1)
    total_income = income_cats.sum(axis=1)

    monthly = pd.DataFrame(
        {
            "total_expense": total_expense,
            "total_income": total_income,
        }
    )
    # Align to the union of both indices (months present in either file).
    monthly = (
        monthly.reindex(expense_cats.index.union(income_cats.index))
        .fillna(0.0)
        .sort_index()
    )
    monthly["net"] = monthly["total_income"] - monthly["total_expense"]

    # Reindex category frames onto the shared month index for consistent slicing.
    expense_cats = expense_cats.reindex(monthly.index).fillna(0.0)
    income_cats = income_cats.reindex(monthly.index).fillna(0.0)

    return FinanceData(
        expense_cats=expense_cats,
        income_cats=income_cats,
        monthly=monthly,
    )

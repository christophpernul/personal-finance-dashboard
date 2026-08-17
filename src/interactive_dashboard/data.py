"""Data loading and aggregation.

The source CSVs are **tidy transaction tables** — one row per transaction:

``date;tag;category;amount`` (German locale: ``;`` separator, ``,`` decimal).

* expenses: ``amount`` is negative (e.g. ``-15,54``)
* incomes:  ``amount`` is positive

This module keeps the raw transactions (for per-category drill-down) and derives
the monthly, per-category aggregates the figure builders consume. All amounts are
exposed as **positive magnitudes**; ``net`` keeps its natural sign.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config


def _load_transactions(path: Path) -> pd.DataFrame:
    """Read one German-locale, semicolon-separated transaction CSV into a tidy
    frame with columns ``date`` (Timestamp), ``month`` (month-start Timestamp),
    ``tag``, ``category`` and numeric ``amount`` (original sign preserved)."""
    df = pd.read_csv(
        path,
        sep=config.CSV_SEP,
        decimal=config.CSV_DECIMAL,
        parse_dates=[config.DATE_COLUMN],
    )
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    for col in ("tag", "category"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
        else:
            df[col] = ""
    df = df.rename(columns={config.DATE_COLUMN: "date"})
    # Month bucket as a month-start timestamp so all months align consistently.
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    return df.sort_values("date").reset_index(drop=True)


def _pivot_cats(txns: pd.DataFrame) -> pd.DataFrame:
    """month x category matrix of summed (positive) amounts."""
    if txns.empty:
        return pd.DataFrame()
    piv = txns.pivot_table(
        index="month",
        columns="category",
        values="amount",
        aggfunc="sum",
        fill_value=0.0,
    )
    piv.index.name = "month"
    return piv.sort_index()


@dataclass
class FinanceData:
    """In-memory, ready-to-slice view of the cashflow data.

    All amounts are stored as **positive magnitudes** for expenses and income.
    ``net`` keeps its natural sign (income - expenses).
    """

    expense_cats: pd.DataFrame  # month x category, positive magnitudes
    income_cats: pd.DataFrame  # month x category, positive magnitudes
    monthly: pd.DataFrame  # month-indexed: total_expense, total_income, net
    expense_txns: pd.DataFrame  # tidy: date, month, tag, category, amount (>0)
    income_txns: pd.DataFrame  # tidy: date, month, tag, category, amount (>0)

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

    def _txns(self, kind: str) -> pd.DataFrame:
        if kind == "expenses":
            return self.expense_txns
        if kind == "income":
            return self.income_txns
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
        et = (self.expense_txns["month"] >= start) & (
            self.expense_txns["month"] <= end
        )
        it = (self.income_txns["month"] >= start) & (
            self.income_txns["month"] <= end
        )
        return FinanceData(
            expense_cats=self.expense_cats.loc[e],
            income_cats=self.income_cats.loc[i],
            monthly=self.monthly.loc[m],
            expense_txns=self.expense_txns.loc[et],
            income_txns=self.income_txns.loc[it],
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

    def transactions(
        self, kind: str, category: str, month: pd.Timestamp | None = None
    ) -> pd.DataFrame:
        """Individual transactions for ``category`` within the (already sliced)
        period, newest first. Pass ``month`` to restrict to a single month.

        Columns: ``date``, ``tag``, ``amount`` (positive magnitude).
        """
        txns = self._txns(kind)
        if txns.empty:
            return txns.loc[:, ["date", "tag", "amount"]]
        sel = txns[txns["category"] == category]
        if month is not None:
            sel = sel[sel["month"] == month]
        sel = sel.sort_values("date", ascending=False)
        return sel.loc[:, ["date", "tag", "amount"]]


def load_finance_data(data_dir: Path | None = None) -> FinanceData:
    """Load transactions and derive monthly aggregates from ``data_dir``."""
    data_dir = Path(data_dir) if data_dir is not None else config.DATA_DIR
    expenses_path = data_dir / config.EXPENSES_FILE
    incomes_path = data_dir / config.INCOMES_FILE
    for p in (expenses_path, incomes_path):
        if not p.exists():
            raise FileNotFoundError(
                f"Cashflow data not found: {p}\n"
                f"Set FINANCE_DATA_DIR or place the CSVs there."
            )

    raw_expenses = _load_transactions(expenses_path)  # negative amounts
    raw_incomes = _load_transactions(incomes_path)  # positive amounts

    # Positive magnitudes for both.
    expense_txns = raw_expenses.assign(amount=raw_expenses["amount"].abs())
    income_txns = raw_incomes.assign(amount=raw_incomes["amount"].abs())

    expense_cats = _pivot_cats(expense_txns)
    income_cats = _pivot_cats(income_txns)

    total_expense = expense_cats.sum(axis=1)
    total_income = income_cats.sum(axis=1)

    monthly = pd.DataFrame(
        {
            "total_expense": total_expense,
            "total_income": total_income,
        }
    )
    # Align to the union of both indices (months present in either file).
    month_index = expense_cats.index.union(income_cats.index)
    monthly = monthly.reindex(month_index).fillna(0.0).sort_index()
    monthly["net"] = monthly["total_income"] - monthly["total_expense"]

    # Reindex category frames onto the shared month index for consistent slicing.
    expense_cats = expense_cats.reindex(month_index).fillna(0.0)
    income_cats = income_cats.reindex(month_index).fillna(0.0)

    return FinanceData(
        expense_cats=expense_cats,
        income_cats=income_cats,
        monthly=monthly,
        expense_txns=expense_txns,
        income_txns=income_txns,
    )

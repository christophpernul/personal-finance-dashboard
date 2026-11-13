"""Cash: loading and aggregation.

Three transform tables of the datahub (the dashboard computes no interest):

- ``transform_cash__balances_monthly.csv`` — balance of every account per month
  end with its current interest rate; ``balance_date`` is the date of the
  recorded balance used and ``is_stale`` flags an outdated one.
- ``transform_cash__term_deposits.csv`` — one row per fixed-term deposit with
  status (``läuft`` / ``abgelaufen`` / ``zukünftig``), days left and progress.
- ``transform_cash__liquidity_monthly.csv`` — all cash per month end split into
  ``verfügbar`` (accounts) and ``gebunden`` (fixed-term deposits); months after
  the current one are a projection until the last deposit matures. Credit card
  and loan balances (``is_liability``, negative) come as ``verbindlichkeiten``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config

logger = logging.getLogger(__name__)

STATUS_RUNNING = "läuft"
STATUS_MATURED = "abgelaufen"
STATUS_UPCOMING = "zukünftig"
STATUS_LABELS = {
    STATUS_RUNNING: "Running",
    STATUS_MATURED: "Matured",
    STATUS_UPCOMING: "Upcoming",
}
BUCKET_AVAILABLE = "verfügbar"
BUCKET_BOUND = "gebunden"
BUCKET_LIABILITIES = "verbindlichkeiten"


@dataclass
class CashData:
    accounts: pd.DataFrame  # latest month: one row per cash account
    liabilities: pd.DataFrame  # latest month: credit cards and loans
    deposits: pd.DataFrame  # one row per fixed-term deposit
    # month x [available, bound, liabilities, is_projection]
    liquidity: pd.DataFrame

    @property
    def available(self) -> float:
        return float(self.accounts["balance"].sum())

    @property
    def owed(self) -> float:
        """Sum of the liability balances (negative when money is owed)."""
        return float(self.liabilities["balance"].sum())

    @property
    def net(self) -> float:
        """Available plus bound cash minus what is owed."""
        return self.available + self.bound + self.owed

    @property
    def running_deposits(self) -> pd.DataFrame:
        return self.deposits[self.deposits["status"] == STATUS_RUNNING]

    @property
    def bound(self) -> float:
        return float(self.running_deposits["principal"].sum())

    @property
    def as_of(self) -> pd.Timestamp | None:
        """Date of the most recent recorded balance."""
        dates = pd.concat(
            [self.accounts["balance_date"], self.liabilities["balance_date"]]
        )
        return None if dates.empty else dates.max()

    def next_maturity(self) -> pd.Series | None:
        """The running or upcoming deposit that matures next."""
        open_ = self.deposits[self.deposits["status"] != STATUS_MATURED]
        if open_.empty:
            return None
        return open_.sort_values("end_date").iloc[0]

    def weighted_rate(self) -> float:
        """Average interest rate of all cash (accounts + running deposits),
        weighted by amount; accounts without a rate count as 0 %."""
        amounts = pd.concat(
            [self.accounts["balance"], self.running_deposits["principal"]]
        )
        rates = pd.concat(
            [self.accounts["rate_pa"], self.running_deposits["rate_pa"]]
        ).fillna(0.0)
        total = amounts.sum()
        return (
            float((amounts * rates).sum() / total) if total else float("nan")
        )


def _read_csv(path: Path, date_cols: list[str]) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep=config.CSV_SEP,
        decimal=config.CSV_DECIMAL,
        parse_dates=date_cols,
    )


def _as_bool(values: pd.Series) -> pd.Series:
    """The CSVs store booleans as text."""
    return values.astype(str).str.lower() == "true"


def load_cash_data(directory: Path | None = None) -> CashData | None:
    """Load the cash tables; None if the datahub has not created them yet, so
    the rest of the dashboard still starts."""
    directory = (
        Path(directory) if directory is not None else config.TRANSFORM_DIR
    )
    paths = [
        directory / config.CASH_BALANCES_FILE,
        directory / config.CASH_TERM_DEPOSITS_FILE,
        directory / config.CASH_LIQUIDITY_FILE,
    ]
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        logger.warning(f"Cash data not found in {directory}: {missing}")
        return None
    balances_path, deposits_path, liquidity_path = paths

    balances = _read_csv(
        balances_path, ["date", "balance_date", "rate_valid_until"]
    )
    balances["is_stale"] = _as_bool(balances["is_stale"])
    if "is_liability" in balances.columns:
        balances["is_liability"] = _as_bool(balances["is_liability"])
    else:  # tables written before liabilities were tracked
        balances["is_liability"] = False
    latest = balances[balances["date"] == balances["date"].max()]
    latest = latest.sort_values("balance", ascending=False)
    accounts = latest[~latest["is_liability"]].reset_index(drop=True)
    liabilities = (
        latest[latest["is_liability"]]
        .sort_values("balance")
        .reset_index(drop=True)
    )

    deposits = _read_csv(deposits_path, ["start_date", "end_date"])
    rank = {STATUS_RUNNING: 0, STATUS_UPCOMING: 1, STATUS_MATURED: 2}
    deposits = (
        deposits.assign(_rank=deposits["status"].map(rank))
        .sort_values(["_rank", "end_date"])
        .drop(columns="_rank")
        .reset_index(drop=True)
    )

    liquidity = _read_csv(liquidity_path, ["date"])
    liquidity["is_projection"] = _as_bool(liquidity["is_projection"])
    wide = liquidity.pivot_table(
        index="date", columns="bucket", values="value", aggfunc="sum"
    ).rename(
        columns={
            BUCKET_AVAILABLE: "available",
            BUCKET_BOUND: "bound",
            BUCKET_LIABILITIES: "liabilities",
        }
    )
    wide = wide.reindex(columns=["available", "bound", "liabilities"])
    wide["is_projection"] = liquidity.groupby("date")["is_projection"].any()
    # Before the first recorded balance only the bound money is known, which
    # would read as if there was no cash at all: start with the first balance.
    known = wide["available"].dropna()
    if not known.empty:
        wide = wide.loc[known.index.min() :]
    return CashData(
        accounts=accounts,
        liabilities=liabilities,
        deposits=deposits,
        liquidity=wide,
    )

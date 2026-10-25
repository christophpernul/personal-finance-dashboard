"""Money-weighted average annual returns (XIRR) of the portfolio.

Every cashflow is taken from the investor's view: money paid in is negative,
money received (sell proceeds, dividends) positive, and today's value of a
position counts as if it were sold on its valuation date. The XIRR is the yearly
rate at which these flows discount to zero, so it accounts for when the money
went in (e.g. monthly savings plans), unlike gain / investment.

Sources (transform layer of the datahub):

- ETFs and stocks: ``transform_portfolio__cashflows.csv`` — every trade
  (incl. rebalancing and sold positions), dividend and today's value.
- Crypto as a class: the EUR moved between bank and exchanges
  (``transform_crypto__ledger.csv``) plus today's value of all coins.
- Single coins: the EUR legs of their trades (``transform_crypto__trades.csv``)
  plus today's value (``transform_crypto__coins.csv``). A crypto-to-crypto swap
  has no EUR price in the data and moves the cost basis instead, so a coin bought
  mostly by swapping other coins gets no return of its own.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

FIAT = "EUR"
# Coins whose buy-in came from swaps by more than this share get no return.
MAX_SWAP_SHARE = 0.5


@dataclass
class Returns:
    by_asset: dict[tuple[str, str], float]  # (group, isin or coin) -> % p.a.
    by_group: dict[str, float]  # group label or "All" -> % p.a.


def xirr(dates: pd.Series, amounts: pd.Series) -> float:
    """Yearly rate (in %) at which the flows discount to zero; NaN if the flows
    don't both pay in and pay out."""
    amounts = np.asarray(amounts, dtype=float)
    if not ((amounts < 0).any() and (amounts > 0).any()):
        return math.nan
    dates = pd.to_datetime(pd.Series(dates))
    years = ((dates - dates.min()).dt.days / 365.25).to_numpy()

    def npv(rate: float) -> float:
        return float((amounts / (1.0 + rate) ** years).sum())

    low, high = -0.9999, 1.0
    while npv(high) > 0 and high < 1e6:
        high *= 2
    if npv(low) * npv(high) > 0:
        return math.nan
    for _ in range(100):  # bisection: precise to far below 0.01 %
        mid = (low + high) / 2
        if npv(low) * npv(mid) <= 0:
            high = mid
        else:
            low = mid
    return (low + high) / 2 * 100


def _read_csv(name: str) -> pd.DataFrame:
    path = config.TRANSFORM_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"Portfolio data not found: {path}\n"
            f"Set FINANCE_TRANSFORM_DIR or place the CSV there."
        )
    return pd.read_csv(
        path,
        sep=config.CSV_SEP,
        decimal=config.CSV_DECIMAL,
        parse_dates=["date"],
    )


def _security_flows(group_labels: dict[str, str]) -> pd.DataFrame:
    """[group, asset, date, amount] of every ETF and stock."""
    flows = _read_csv(config.PORTFOLIO_CASHFLOWS_FILE)
    return pd.DataFrame(
        {
            "group": flows["security_type"].map(group_labels),
            "asset": flows["isin"],
            "date": flows["date"],
            "amount": flows["amount"],
        }
    )


def _crypto_flows(group: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Flows of the crypto class [date, amount] and per coin [group, asset,
    date, amount]."""
    coins = _read_csv(config.CRYPTO_COINS_FILE)
    values = pd.DataFrame(
        {
            "asset": coins["coin"],
            "date": coins["date"],
            "amount": coins["value"].fillna(0.0),
        }
    )

    ledger = _read_csv(config.CRYPTO_LEDGER_FILE)
    bank = ledger[
        (ledger["coin"] == FIAT)
        & ledger["type"].isin(["deposit", "withdrawal"])
    ]
    class_flows = pd.concat(
        [
            # a deposit (+EUR on the exchange) is money paid in
            pd.DataFrame({"date": bank["date"], "amount": -bank["amount"]}),
            pd.DataFrame(
                {
                    "date": [values["date"].max()],
                    "amount": [values["amount"].sum()],
                }
            ),
        ],
        ignore_index=True,
    )

    trades = _read_csv(config.CRYPTO_TRADES_FILE)
    sale = trades["coin_bought"] == FIAT
    swap = (trades["coin_sold"] != FIAT) & ~sale
    legs = [
        # coin bought: pays the EUR spent or, in a swap, the cost basis moved
        pd.DataFrame(
            {
                "asset": trades["coin_bought"],
                "date": trades["date"],
                "amount": -trades["cost_basis"],
            }
        )[~sale],
        # coin sold: receives the EUR proceeds or, in a swap, its cost basis
        pd.DataFrame(
            {
                "asset": trades["coin_sold"],
                "date": trades["date"],
                "amount": trades["amount_bought"].where(
                    sale, trades["cost_basis"]
                ),
            }
        )[trades["coin_sold"] != FIAT],
        # fees are charged to the coin bought, or the coin sold for EUR
        pd.DataFrame(
            {
                "asset": trades["coin_sold"].where(
                    sale, trades["coin_bought"]
                ),
                "date": trades["date"],
                "amount": -trades["fee_eur"],
            }
        ),
        values,
    ]
    coin_flows = pd.concat(legs, ignore_index=True)
    coin_flows = coin_flows[coin_flows["asset"] != FIAT]

    swap_share = (
        trades[swap].groupby("coin_bought")["cost_basis"].sum()
        / trades[~sale].groupby("coin_bought")["cost_basis"].sum()
    )
    swapped = swap_share[swap_share > MAX_SWAP_SHARE].index
    coin_flows = coin_flows[~coin_flows["asset"].isin(swapped)]
    return class_flows, coin_flows.assign(group=group)


def compute_returns(
    group_labels: dict[str, str], crypto_group: str
) -> Returns:
    """Annual returns per asset, per group and of everything ("All")."""
    securities = _security_flows(group_labels)
    crypto_class, coins = _crypto_flows(crypto_group)

    by_asset = {
        key: xirr(flows["date"], flows["amount"])
        for key, flows in pd.concat([securities, coins]).groupby(
            ["group", "asset"]
        )
    }
    by_group = {
        group: xirr(flows["date"], flows["amount"])
        for group, flows in securities.groupby("group")
    }
    by_group[crypto_group] = xirr(crypto_class["date"], crypto_class["amount"])
    everything = pd.concat([securities, crypto_class], ignore_index=True)
    by_group["All"] = xirr(everything["date"], everything["amount"])
    return Returns(by_asset=by_asset, by_group=by_group)

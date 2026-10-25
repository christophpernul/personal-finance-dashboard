"""Portfolio positions: loading and aggregation.

Two sources from the transform layer, both with one row per open position and
its current price/value and the amount invested:

- ``transform_portfolio__value.csv`` — ETFs and stocks with master data (ISIN,
  symbol, type, currency), grouped via ``security_type``.
- ``transform_crypto__portfolio_value.csv`` — coins (and EUR cash) per
  exchange or wallet they are held on.

Every position gets an ``exchange``: for crypto the exchange/wallet holding it,
for ETFs and stocks the stock exchange of its ticker symbol, and an
``annual_return``: its money-weighted average annual return (see returns.py).

Note: the snapshot date can differ per group (e.g. ETFs current, stocks from an
earlier scrape), so the ``as_of`` date is kept and surfaced in the UI.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config
from .returns import Returns, compute_returns

# Map the raw security_type to a clean, English group label.
GROUP_LABELS = {"ETF": "ETFs", "Aktie": "Stocks"}
CRYPTO_GROUP = "Crypto"
GROUP_ORDER = ["ETFs", "Stocks", CRYPTO_GROUP]

# Ticker suffix -> stock exchange (same names as ``exchange_name`` in the ETF
# master data). Tickers without a suffix are US listings.
EXCHANGE_BY_SUFFIX = {
    "DE": "XETRA",
    "L": "LSE",
    "AS": "Amsterdam",
    "PA": "Paris",
    "SG": "Stuttgart",
    "MI": "Milan",
    "SW": "Swiss",
}
US_EXCHANGE = "US"

# Crypto exchange/wallet ids whose display name isn't just capitalized.
CRYPTO_EXCHANGE_LABELS = {"kucoin": "KuCoin", "myetherwallet": "MyEtherWallet"}

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

# Crypto columns that differ from the ETF/stock ones (the rest match _RENAME).
_CRYPTO_RENAME = {
    **_RENAME,
    "coin": "symbol",
    "amount": "shares",
    "symbol": "ticker",
}

# Order of columns shown in the positions table.
DISPLAY_COLUMNS = [
    "group",
    "name",
    "symbol",
    "isin",
    "exchange",
    "currency",
    "shares",
    "price",
    "investment",
    "value",
    "gain",
    "gain_pct",
    "annual_return",
    "as_of",
]

_NUMERIC = ["shares", "price", "value", "investment", "gain", "gain_pct"]


@dataclass
class PortfolioData:
    positions: pd.DataFrame  # one tidy row per position (see _RENAME/DISPLAY_COLUMNS)
    returns: Returns  # money-weighted annual returns (see returns.py)

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
        agg["annual_return"] = agg.index.map(self.returns.by_group)
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


def _read_csv(path: Path) -> pd.DataFrame:
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


def _stock_exchange(symbol: str) -> str:
    """Stock exchange of a ticker like ``EUEA.AS`` (no suffix = US)."""
    if not isinstance(symbol, str) or "." not in symbol:
        return US_EXCHANGE
    suffix = symbol.rsplit(".", 1)[1]
    return EXCHANGE_BY_SUFFIX.get(suffix, suffix)


def _load_securities(path: Path) -> pd.DataFrame:
    df = _read_csv(path).rename(columns=_RENAME)
    df["group"] = (
        df["security_type"].map(GROUP_LABELS).fillna(df["security_type"])
    )
    df["exchange"] = df["symbol"].map(_stock_exchange)
    # Exchange quotes are in cents; drop the float noise of the price scrape.
    df["price"] = pd.to_numeric(df["price"], errors="coerce").round(2)
    return df


def _load_crypto(path: Path) -> pd.DataFrame:
    df = _read_csv(path).rename(columns=_CRYPTO_RENAME)
    df["group"] = CRYPTO_GROUP
    df["isin"] = ""
    df["exchange"] = df["exchange"].map(
        lambda e: CRYPTO_EXCHANGE_LABELS.get(e, e.capitalize())
    )
    return df


def load_portfolio_data(
    path: Path | None = None, crypto_path: Path | None = None
) -> PortfolioData:
    """Load and tidy the ETF/stock and crypto positions CSVs."""
    path = (
        Path(path)
        if path is not None
        else config.TRANSFORM_DIR / config.PORTFOLIO_FILE
    )
    crypto_path = (
        Path(crypto_path)
        if crypto_path is not None
        else config.TRANSFORM_DIR / config.CRYPTO_PORTFOLIO_FILE
    )

    df = pd.concat(
        [_load_securities(path), _load_crypto(crypto_path)],
        ignore_index=True,
    )
    for col in _NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Crypto positions are keyed by coin, ETFs/stocks by ISIN (stocks: name).
    returns = compute_returns(GROUP_LABELS, CRYPTO_GROUP)
    asset = df["symbol"].where(df["group"] == CRYPTO_GROUP, df["isin"])
    df["annual_return"] = [
        returns.by_asset.get(key, math.nan) for key in zip(df["group"], asset)
    ]

    rank = {grp: i for i, grp in enumerate(GROUP_ORDER)}
    df = (
        df[DISPLAY_COLUMNS]
        .assign(_rank=df["group"].map(rank).fillna(len(rank)))
        .sort_values(
            ["_rank", "group", "value"], ascending=[True, True, False]
        )
        .drop(columns="_rank")
        .reset_index(drop=True)
    )

    return PortfolioData(positions=df, returns=returns)

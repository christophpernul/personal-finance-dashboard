"""
This is the central location, where the dash app is initiated. It is loaded in all necessary files
defining the app layouts from here, in order to use callbacks beside the main_app.py file. If this is
not structured this way the callbacks in subsequent files are not executed. (https://dash.plotly.com/urls)
See: https://community.plotly.com/t/dash-callback-in-a-separate-file/14122
"""
import dash
import dash_bootstrap_components as dbc
import pandas as pd
from pathlib import Path

# TODO: All datahub functionalities need to be dropped!
from utils.file_io import load_data

from src.datahub.processing_layer.lib_data_operations import (
    preprocess_etf_masterdata,
    preprocess_orders,
    enrich_orders,
    get_current_portfolio,
    prepare_timeseries,
    get_portfolio_value,
)

# from datahub.datahub_crypto.extract_crypto_data import get_current_cryptocurrency_price
app = dash.Dash(
    __name__,
    title="Finance App",
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.SLATE],
)
server = app.server

################################ Data Processing for ETF portfolio #####################################################
# TODO: Load only necessary data and drop everything else! Use load_data() function instead!
DATAHUB_ROOT_FILEPATH = "D:/SynologyDrive/Finance/data/datahub/"
df_expenses = pd.read_csv(
    filepath_or_buffer=f"{DATAHUB_ROOT_FILEPATH}target/cashflow/B00_expenses.csv"
)
df_incomes = pd.read_csv(
    filepath_or_buffer=f"{DATAHUB_ROOT_FILEPATH}target/cashflow/B00_incomes.csv"
)
df_expenses["date"] = pd.to_datetime(df_expenses["date"], format="%Y-%m-%d")
df_expenses = df_expenses.set_index("date")
df_incomes["date"] = pd.to_datetime(df_incomes["date"], format="%Y-%m-%d")
df_incomes = df_incomes.set_index("date")

# Prepare cashflow data
df_expenses_copy = df_expenses.copy()
df_expenses_copy["total"] = df_expenses_copy.sum(axis=1)
df_expenses_copy = df_expenses_copy[["total"]]

df_incomes_copy = df_incomes.copy()
df_incomes_copy["total"] = df_incomes_copy.sum(axis=1)
df_incomes_copy = df_incomes_copy[["total"]]

df_cashflow = df_incomes_copy + df_expenses_copy

# TODO: Drop this empty data for unused tabs!
portfolio_crypto_value = pd.DataFrame()

# ---------------- EXTRACT --------------------
filepath_source = Path(DATAHUB_ROOT_FILEPATH) / "source" / "stocks"
orders_init = load_data(
    filepath_source / "source_stocks_portfolio_trades.ods",
    file_type="excel",
    sheet_name="Buys",
)
sells_init = load_data(
    filepath_source / "source_stocks_portfolio_trades.ods",
    file_type="excel",
    sheet_name="Sells",
)
master_data_init = load_data(filepath_source / "source_master_data.csv")
current_etf_prices = load_data(
    filepath_source / "source_etf_price_current.csv"
)
historic_etf_prices = load_data(
    filepath_source / "source_etf_price_historic.csv"
)

# crypto_prices = get_current_cryptocurrency_price(currency="EUR")

# ----------------- PREPROCESS --------------------
orders = preprocess_orders(orders_init, type="buys")
sells = preprocess_orders(sells_init, type="sells")
master_data = preprocess_etf_masterdata(master_data_init)

# -------------- TRANSFORM ----------------------
all_orders = pd.concat([orders, sells], ignore_index=True)
orders_enriched = enrich_orders(all_orders, master_data)
current_portfolio = get_current_portfolio(orders_enriched)
portfolio_value = get_portfolio_value(orders_enriched, current_etf_prices)

# TODO: UNderstand how prices were used before restructuring. From manual data or historic?
df_timeseries = prepare_timeseries(orders_enriched)

print("Done")
# portfolio_crypto_value = pl.compute_crypto_portfolio_value(portfolio_crypto, crypto_prices)

"""
This is the central location, where the dash app is initiated. It is loaded in all necessary files
defining the app layouts from here, in order to use callbacks beside the main_app.py file. If this is
not structured this way the callbacks in subsequent files are not executed. (https://dash.plotly.com/urls)
See: https://community.plotly.com/t/dash-callback-in-a-separate-file/14122
"""
import dash
import dash_bootstrap_components as dbc
import pandas as pd

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
    filepath_or_buffer=f"{DATAHUB_ROOT_FILEPATH}target/target_cashflow__expenses.csv",
    sep=";",
    decimal=",",
)
df_incomes = pd.read_csv(
    filepath_or_buffer=f"{DATAHUB_ROOT_FILEPATH}target/target_cashflow__incomes.csv",
    sep=";",
    decimal=",",
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

# ---------------- LOAD PRECALCULATED PORTFOLIO DATA --------------------
# Reuse the tables the datahub already computes instead of preprocessing here.
portfolio_value = pd.read_csv(
    filepath_or_buffer=f"{DATAHUB_ROOT_FILEPATH}transform/transform_etf__portfolio_value.csv",
    sep=";",
    decimal=",",
)

# TODO: The current portfolio (current holdings per position) is not yet
#       produced by the datahub. Calculate it there first, then load it from
#       disk here instead of this empty placeholder.
current_portfolio = pd.DataFrame()

# TODO: The portfolio price timeseries is not yet produced by the datahub.
#       Calculate it there, load it from disk, and re-enable the
#       "Portfolio Timeseries" tab (main_app.py) together with the trade data
#       (`orders`) that fed its stock selector.
# orders = <preprocessed trades>
# df_timeseries = <prepare_timeseries(orders_enriched)>

# crypto_prices = get_current_cryptocurrency_price(currency="EUR")
# portfolio_crypto_value = pl.compute_crypto_portfolio_value(portfolio_crypto, crypto_prices)

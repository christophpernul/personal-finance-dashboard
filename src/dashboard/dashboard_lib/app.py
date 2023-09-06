"""
This is the central location, where the dash app is initiated. It is loaded in all necessary files
defining the app layouts from here, in order to use callbacks beside the main_app.py file. If this is
not structured this way the callbacks in subsequent files are not executed. (https://dash.plotly.com/urls)
See: https://community.plotly.com/t/dash-callback-in-a-separate-file/14122
"""
import dash
import dash_bootstrap_components as dbc
import pandas as pd
# from src.datahub.processing_layer import lib_data_operations as pl
# from src.datahub.datahub_crypto.extract_crypto_data import get_current_cryptocurrency_price
# TODO: Use poetry here too!
app = dash.Dash(__name__,
                title="Finance App",
                suppress_callback_exceptions=True,
                external_stylesheets=[dbc.themes.SLATE]
                )
server = app.server

################################ Data Processing for ETF portfolio #####################################################
# TODO: Load only necessary data and drop everything else! Use load_data() function instead!
df_expenses = pd.read_csv(filepath_or_buffer="C:/Users/pernulio/Dropbox/Finance/data/datahub/transform/cashflow/a_20_incomes.csv")
df_incomes = pd.read_csv(filepath_or_buffer="C:/Users/pernulio/Dropbox/Finance/data/datahub/transform/cashflow/a_20_expenses.csv")
df_expenses["Date"] = pd.to_datetime(df_expenses["Date"], format='%Y-%m-%d')
df_expenses = df_expenses.set_index("Date")
df_incomes["Date"] = pd.to_datetime(df_incomes["Date"], format='%Y-%m-%d')
df_incomes = df_incomes.set_index("Date")

df_orders = pd.DataFrame()
df_timeseries = pd.DataFrame()
portfolio_crypto_value = pd.DataFrame()
portfolio_monthly = pd.DataFrame()
portfolio_value = pd.DataFrame()

# (df_etf_init, df_orders_init, df_dividends, df_income_init, df_prices_init, \
#     df_cashflow_init, _, portfolio_crypto) = pl.load_data()
# crypto_prices = get_current_cryptocurrency_price(currency="EUR")

# df_orders = pl.preprocess_orders(df_orders_init)
# df_prices = pl.preprocess_prices(df_prices_init)
# df_etf = pl.preprocess_etf_masterdata(df_etf_init)
# df_cashflow = pl.cleaning_cashflow(df_cashflow_init)
# (incomes, expenses) = pl.split_cashflow_data(df_cashflow)
# (caution_expenses, df_expenses) = pl.preprocess_cashflow(expenses)
# df_income_total = pl.combine_incomes(incomes, df_income_init)
# (caution_income, df_incomes) = pl.preprocess_cashflow(df_income_total)


# orders_etf = pl.enrich_orders(df_orders, df_etf)
# portfolio_monthly = pl.get_current_portfolio(orders_etf)
# portfolio_value = pl.get_portfolio_value(orders_etf, df_prices)
#
# portfolio_crypto_value = pl.compute_crypto_portfolio_value(portfolio_crypto, crypto_prices)
#
#
# df_timeseries = pl.prepare_timeseries(df_orders)


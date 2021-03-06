"""
This is the central location, where the dash app is initiated. It is loaded in all necessary files
defining the app layouts from here, in order to use callbacks beside the main_app.py file. If this is
not structured this way the callbacks in subsequent files are not executed. (https://dash.plotly.com/urls)
See: https://community.plotly.com/t/dash-callback-in-a-separate-file/14122
"""
import dash
import dash_bootstrap_components as dbc
import lib_data_operations as pl
import lib_finance as lf

app = dash.Dash(__name__,
                title="Finance App",
                suppress_callback_exceptions=True,
                external_stylesheets=[dbc.themes.SLATE]
                )
server = app.server

################################ Data Processing for ETF portfolio #####################################################
(df_etf_init, df_orders_init, df_dividends, df_income_init, df_prices_init, \
    df_cashflow_init, _, df_crypto_deposits_init, df_crypto_trades_init) = pl.load_data()
crypto_prices = lf.get_current_cryptocurrency_price(currency="EUR")

df_orders = pl.preprocess_orders(df_orders_init)
df_prices = pl.preprocess_prices(df_prices_init)
df_etf = pl.preprocess_etf_masterdata(df_etf_init)
df_cashflow = pl.cleaning_cashflow(df_cashflow_init)
(incomes, expenses) = pl.split_cashflow_data(df_cashflow)
(caution_expenses, df_expenses) = pl.preprocess_cashflow(expenses)
df_income_total = pl.combine_incomes(incomes, df_income_init)
(caution_income, df_incomes) = pl.preprocess_cashflow(df_income_total)

orders_etf = pl.enrich_orders(df_orders, df_etf)
portfolio_monthly = pl.get_current_portfolio(orders_etf)
portfolio_value = pl.get_portfolio_value(orders_etf, df_prices)

(df_crypto_deposits, df_crypto_trades_init) = pl.preprocess_crypto_data(df_crypto_deposits_init, df_crypto_trades_init)
portfolio_crypto = pl.compute_crypto_portfolio(df_crypto_deposits, df_crypto_trades_init)
portfolio_crypto_value = pl.compute_crypto_portfolio_value(portfolio_crypto, crypto_prices)

df_timeseries = pl.prepare_timeseries(df_orders)


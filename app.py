"""
This is the central location, where the dash app is initiated. It is loaded in all necessary files
defining the app layouts from here, in order to use callbacks beside the main_app.py file. If this is
not structured this way the callbacks in subsequent files are not executed. (https://dash.plotly.com/urls)
See: https://community.plotly.com/t/dash-callback-in-a-separate-file/14122
"""
import dash
import dash_bootstrap_components as dbc
import lib_data_operations as pl

app = dash.Dash(__name__,
                title="Finance App",
                suppress_callback_exceptions=True,
                external_stylesheets=[dbc.themes.SLATE]
                )
server = app.server

################################ Data Processing for ETF portfolio #####################################################
(df_etf_init, df_orders_init, df_income, df_prices_init, df_cashflow_init, _) = pl.load_data()

(df_orders, _) = pl.preprocess_orders(df_orders_init)
df_prices = pl.preprocess_prices(df_prices_init)
df_etf = pl.preprocess_etf_masterdata(df_etf_init)
(df_cashflow, _) = pl.cleaning_cashflow(df_cashflow_init)
(incomes, expenses) = pl.split_cashflow_data(df_cashflow)
(_, df_expenses) = pl.preprocess_cashflow(expenses)

orders_etf = pl.enrich_orders(df_orders, df_etf)
portfolio_monthly = pl.get_current_portfolio(orders_etf)
portfolio_value = pl.get_portfolio_value(orders_etf, df_prices)

df_timeseries = pl.prepare_timeseries(df_orders)
import dash
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

import tab_portfolio_overview
import lib_portfolio as pl

################################ Data Processing for ETF portfolio #####################################################
(df_etf_init, df_orders_init, _, _) = pl.load_data()
(df_orders, _) = pl.preprocess_orders(df_orders_init)
df_etf = pl.preprocess_etf_masterdata(df_etf_init)
orders_etf = pl.enrich_orders(df_orders, df_etf)
portfolio_monthly = pl.get_current_portfolio(orders_etf)

################################ Define Dash App configuration ### #####################################################
app = dash.Dash(__name__, title="Finance App", external_stylesheets=[dbc.themes.SLATE])
server = app.server

tab_nav_bar = dbc.Tabs(id="tab-navbar",
                       active_tab="tab-expenses",
                       children=[
                                dbc.Tab(label="Ausgaben", tab_id="tab-expenses"),
                                dbc.Tab(label="Einnahmen", tab_id="tab-income")
                                ]
                       )

body = html.Div(
    [tab_nav_bar,
     html.Div(id="tab-content")]
)

app.layout = html.Div([body])

@app.callback(Output('tab-content', 'children'),
              Input('tab-navbar', 'active_tab'))
def switch_tabs(tab):
    if tab == "tab-expenses":
        html_div = tab_portfolio_overview.html_portfolio_overview(portfolio_monthly)
        return(html_div)
    elif tab == "tab-income":
        html_div = html.Div("Income")
        return(html_div)

if __name__ == '__main__':
    app.run_server(debug=True)
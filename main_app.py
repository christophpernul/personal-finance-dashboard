import dash
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

import lib_dash_pages
import lib_data_operations as pl

################################ Data Processing for ETF portfolio #####################################################
(df_etf_init, df_orders_init, df_income, df_prices_init, _) = pl.load_data()

(df_orders, _) = pl.preprocess_orders(df_orders_init)
df_prices = pl.preprocess_prices(df_prices_init)
df_etf = pl.preprocess_etf_masterdata(df_etf_init)

orders_etf = pl.enrich_orders(df_orders, df_etf)
portfolio_monthly = pl.get_current_portfolio(orders_etf)
portfolio_value = pl.get_portfolio_value(orders_etf, df_prices)

################################ Define Dash App configuration ### #####################################################
app = dash.Dash(__name__, title="Finance App", external_stylesheets=[dbc.themes.SLATE])
server = app.server

tab_nav_bar = \
                    dbc.Tabs(id="tab-navbar",
                             active_tab="tab-expenses",
                             children=[
                                        dbc.Tab(label="Monatlicher Sparplan", tab_id="tab-expenses"),
                                        dbc.Tab(label="Portfolio Statistiken", tab_id="tab-income")
                                      ],
                             card=True
                             )

body = [dbc.CardHeader(tab_nav_bar),
        dbc.CardBody(html.Div(id="tab-content"))
]

app.layout = dbc.Card(body)

@app.callback(Output('tab-content', 'children'),
              Input('tab-navbar', 'active_tab'))
def switch_tabs(tab):
    if tab == "tab-expenses":
        group_cols = ["Region", "Type", "Ausschüttung", "Replikationsmethode"]
        compute_cols = ["Betrag", "Betrag", "Betrag", "Betrag"]
        agg_functions = ["sum", "sum", "sum", "sum"]
        html_div = lib_dash_pages.html_portfolio_overview(portfolio_monthly,
                                                          group_cols,
                                                          compute_cols,
                                                          agg_functions
                                                          )
        return(html_div)
    elif tab == "tab-income":
        group_cols = ["Region", "Type", "Ausschüttung", "Replikationsmethode"]
        compute_cols = ["Wert", "Wert", "Wert", "Wert"]
        agg_functions = ["sum", "sum", "sum", "sum"]
        html_div = lib_dash_pages.html_portfolio_overview(portfolio_value,
                                                          group_cols,
                                                          compute_cols,
                                                          agg_functions,
                                                          cost_column_name="Wert",
                                                          title="Gesamtportfolio",
                                                          title_kpi_cost="Gesamter Wert"
                                                          )
        return(html_div)

if __name__ == '__main__':
    app.run_server(debug=True)
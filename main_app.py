import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

from app import app
import apps_portfolio
import lib_data_operations as pl

################################ Data Processing for ETF portfolio #####################################################
(df_etf_init, df_orders_init, df_income, df_prices_init, _) = pl.load_data()

(df_orders, _) = pl.preprocess_orders(df_orders_init)
df_prices = pl.preprocess_prices(df_prices_init)
df_etf = pl.preprocess_etf_masterdata(df_etf_init)

orders_etf = pl.enrich_orders(df_orders, df_etf)
portfolio_monthly = pl.get_current_portfolio(orders_etf)
portfolio_value = pl.get_portfolio_value(orders_etf, df_prices)

##################################### Define Dash App layout ###########################################################

tab_nav_bar = \
                    dbc.Tabs(id="tab-navbar",
                             active_tab="tab-timeseries",
                             children=[
                                        dbc.Tab(label="Expenses", tab_id="tab-expenses"),
                                        dbc.Tab(label="Income", tab_id="tab-income"),
                                        dbc.Tab(label="Monthly Plan", tab_id="tab-portfolio-overview"),
                                        dbc.Tab(label="Portfolio Statistics", tab_id="tab-portfolio-value"),
                                        dbc.Tab(label="Portfolio Timeseries", tab_id="tab-timeseries"),
                                        dbc.Tab(label="Cryptocurrencies", tab_id="tab-crypto")
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
        html_div = html.Div("No content yet!")
        return(html_div)
    elif tab == "tab-income":
        html_div = html.Div("No content yet!")
        return(html_div)
    elif tab == "tab-portfolio-overview":
        group_cols = ["Region", "Type", "Distributing", "Replicationmethod"]
        compute_cols = ["Investment", "Investment", "Investment", "Investment"]
        agg_functions = ["sum", "sum", "sum", "sum"]
        html_div = apps_portfolio.html_portfolio_overview(portfolio_monthly,
                                                          group_cols,
                                                          compute_cols,
                                                          agg_functions
                                                          )
        return(html_div)
    elif tab == "tab-portfolio-value":
        group_cols = ["Region", "Type", "Distributing", "Replicationmethod"]
        compute_cols = ["Value", "Value", "Value", "Value"]
        agg_functions = ["sum", "sum", "sum", "sum"]
        html_div = apps_portfolio.html_portfolio_overview(portfolio_value,
                                                          group_cols,
                                                          compute_cols,
                                                          agg_functions,
                                                          cost_column_name="Value",
                                                          title="Overall Portfolio",
                                                          title_kpi_cost="Total Value"
                                                          )
        return(html_div)
    elif tab == "tab-timeseries":
        html_div = apps_portfolio.html_portfolio_value(orders_etf, df_prices)
        return(html_div)
    elif tab == "tab-crypto":
        html_div = html.Div("No content yet!")
        return(html_div)

if __name__ == '__main__':
    app.run_server(debug=True)
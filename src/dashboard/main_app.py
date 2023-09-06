from dash import html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

### Import app and dataframes containing data to display to call necessary functions and define callbacks
from src.dashboard.dashboard_lib.app import app, portfolio_monthly, portfolio_value
from src.dashboard.dashboard_lib import apps_portfolio

HTML_NO_CONTENT = html.Div([html.H2("Choose a timeframe")])
# TODO: Add functionality with each new feature in future, where HTML_NO_CONTENT was placed!
##################################### Define Dash App layout ###########################################################

tab_nav_bar = \
                    dbc.Tabs(id="tab-navbar",
                             active_tab="tab-expenses",

                             children=[
                                        dbc.Tab(label="Expenses", tab_id="tab-expenses"),
                                        dbc.Tab(label="Income", tab_id="tab-income"),
                                        dbc.Tab(label="Monthly Plan", tab_id="tab-portfolio-overview"),
                                        dbc.Tab(label="Portfolio Statistics", tab_id="tab-portfolio-value"),
                                        dbc.Tab(label="Portfolio Timeseries", tab_id="tab-timeseries"),
                                        dbc.Tab(label="Cryptocurrencies", tab_id="tab-crypto"),
                                        dbc.Tab(label="Savings", tab_id="tab-savings")
                                      ],
                             )

body = [dbc.CardHeader(tab_nav_bar),
        dbc.CardBody(html.Div(id="tab-content"))
]

app.layout = dbc.Card(body)

@app.callback(Output('tab-content', 'children'),
              Input('tab-navbar', 'active_tab'))
def switch_tabs(tab):
    if tab == "tab-expenses":
        html_div = apps_portfolio.html_expenses_tab()
        return(html_div)
    elif tab == "tab-income":
        html_div = apps_portfolio.html_income_tab()
        return(html_div)
    elif tab == "tab-portfolio-overview":
        group_cols = ["Region", "Type", "Distributing", "Replicationmethod"]
        compute_cols = ["Investment", "Investment", "Investment", "Investment"]
        agg_functions = ["sum", "sum", "sum", "sum"]
        # This function is called explicitly with data, because it is reused
        # html_div = apps_portfolio.html_portfolio_overview(portfolio_monthly,
        #                                                   group_cols,
        #                                                   compute_cols,
        #                                                   agg_functions
        #                                                   )
        html_div = HTML_NO_CONTENT
        return(html_div)
    elif tab == "tab-portfolio-value":
        group_cols = ["Region", "Type", "Distributing", "Replicationmethod"]
        compute_cols = ["Value", "Value", "Value", "Value"]
        agg_functions = ["sum", "sum", "sum", "sum"]
        # This function is called explicitly with data, because it is reused
        # html_div = apps_portfolio.html_portfolio_overview(portfolio_value,
        #                                                   group_cols,
        #                                                   compute_cols,
        #                                                   agg_functions,
        #                                                   cost_column_name="Value",
        #                                                   title="Overall Portfolio",
        #                                                   title_kpi_cost="Total Value",
        #                                                   show_last_updated=True
        #                                                   )
        html_div = HTML_NO_CONTENT
        return(html_div)
    elif tab == "tab-timeseries":
        # html_div = apps_portfolio.html_portfolio_timeseries()
        html_div = HTML_NO_CONTENT
        return(html_div)
    elif tab == "tab-crypto":
        # html_div = apps_portfolio.html_crypto_overview()
        html_div = HTML_NO_CONTENT
        return(html_div)
    elif tab == "tab-savings":
        html_div = HTML_NO_CONTENT
        return(html_div)

if __name__ == '__main__':
    app.run_server(debug=True)
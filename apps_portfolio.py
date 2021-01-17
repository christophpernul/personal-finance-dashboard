import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import dash_core_components as dcc

### Import app (to define callbacks) and necessary preprocessed data
from app import app, df_orders, orders_etf
import lib_data_operations as pl
import lib_dash_plot as dpl

theme_colors = {
    'background': '#32383E',
    'text': '#FFFFFF'
}

piechart_descriptions = [
    {'values': 'Percentage', 'names': 'Region', 'title': 'Region'},
    {'values': 'Percentage', 'names': 'Type', 'title': 'Type'},
    {'values': 'Percentage', 'names': 'Distributing', 'title': 'Distributing'},
    {'values': 'Percentage', 'names': 'Replicationmethod', 'title': 'Replicationmethod'}
]

def html_portfolio_overview(portfolio,
                            group_columns: list,
                            compute_columns: list,
                            aggregation_columns: list,
                            cost_column_name = "Investment",
                            title = "Overview monthly Savings Plan",
                            title_kpi_cost = "Monthly Investment"
                            ):
    """
    Creates a HTML element that displays four elements as a page:
    Top left: Title of page
    Top right: Two KPI elements:
                Top:
    Middle: Table with overview of current monthly savings plan
    Bottom: Panel of four piecharts showing statistics about Region, Type, Replication method and accumulation
    :param portfolio: dataframe holding transactions
    :param group_columns: Columns used for groupby for piecharts
    :param compute_columns: Columns that are aggregated by groupby
    :param aggregation_columns: Aggregation function for groupby
    :param title: Title of the page
    :param title_kpi_cost: Title of the KPI element showing the total cost of investment
    :return: HTML div element
    """
    ################################ Prepare data for remainder ########################################################
    grouped_portfolio = pl.compute_percentage_per_group(portfolio,
                                                        group_columns,
                                                        compute_columns,
                                                        aggregation_columns
                                                        )

    portfolio_view = portfolio.copy()

    portfolio_view["cost/a"] = 12*portfolio_view[cost_column_name]*portfolio_view["TER%"]/100
    total_costs = round(portfolio_view[cost_column_name].sum(), 2)
    average_TER = round((portfolio_view["cost/a"]/(12*total_costs)).sum()*100, 3)

    portfolio_view = portfolio_view.drop(["cost/a"], axis=1)

    all_group_columns = ["Name", "ISIN", "TER%"]+ group_columns
    portfolio_view = portfolio_view.groupby(all_group_columns).sum()\
                                    .reset_index().sort_values(cost_column_name, ascending=False)

    portfolio_view = portfolio_view[all_group_columns + [cost_column_name]]



    ################################ Define Dash App configuration ### #####################################################

    heading = \
        dbc.Col(
            dbc.Card(
                dbc.CardBody(
                    html.H1(html.B(title))
                ),
            ),
            width=6,
            align='center'
        )

    kpi_panel_top = \
                    html.Div(
                        dbc.Row(
                            [dbc.Col(html.H2("Average TER")),
                             dbc.Col(html.H2(html.B(f"{average_TER} %")))],
                            justify='around'
                ),
            )

    kpi_panel_bottom = \
                    html.Div(
                        dbc.Row(
                            [dbc.Col(html.H2(title_kpi_cost)),
                             dbc.Col(html.H2(html.B(f"{total_costs} €")))],
                            justify='around'
                ),
            )

    kpi_panel = dbc.Col(
        dbc.Card(
            dbc.CardBody(
                html.Div([kpi_panel_top, kpi_panel_bottom])
            ),
        ),
        width=6,
        align='center'
    )

    header_panel = dbc.Row([heading,kpi_panel], justify='around')

    dataframe_panel = \
        dbc.Card(
            dbc.CardBody(
                dpl.show_dataframe(portfolio_view, style_dict=theme_colors)
            ),
        )

    chart_panel = dbc.Row([
                            dbc.Col(dpl.show_piechart(grouped_portfolio[0],
                                                      group_columns[0],
                                                      "Percentage",
                                                       theme_colors),
                                    width=3,
                                    align='center'),
                            dbc.Col(dpl.show_piechart(grouped_portfolio[1],
                                                      group_columns[1],
                                                      "Percentage",
                                                       theme_colors),
                                    width=3,
                                    align='center'),
                            dbc.Col(dpl.show_piechart(grouped_portfolio[2],
                                                      group_columns[2],
                                                      "Percentage",
                                                       theme_colors),
                                    width=3,
                                    align='center'),
                            dbc.Col(dpl.show_piechart(grouped_portfolio[3],
                                                      group_columns[3],
                                                      "Percentage",
                                                       theme_colors),
                                    width=3,
                                    align='center')
                            ],
        justify='around'
    )



    tab_overview = html.Div([header_panel,
                             dataframe_panel,
                             chart_panel
                            ]
                    )
    return(tab_overview)

def html_portfolio_value(title="Portfolio Price Trend"):
    """
    TODO: Compute overall portfolio values in case of "Overall" selected, add this to distinct stocks
    :param title:
    :return:
    """

    dropdown_timespan = dcc.Dropdown(options=[
                                        {"label": "1 Month", "value": 1},
                                        {"label": "3 Months", "value": 3},
                                        {"label": "6 Months", "value": 6},
                                        {"label": "1 Year", "value": 12},
                                        {"label": "5 Years", "value": 60},
                                        {"label": "Full", "value": -1}
                                    ],
                                    value=-1,
                                    id="dropdown-timespan",

    )
    distinct_stocks = list(df_orders["Name"].drop_duplicates().sort_values())

    dropdown_stocks = dcc.Dropdown(options=[
        {"label": stock_name, "value": stock_name} for stock_name in distinct_stocks
    ],
        value=distinct_stocks[0],
        id="dropdown-stocks"
    )
    dropdown_panel = html.Div([html.H2("Choose a timeframe"),
                                dropdown_timespan,
                                 html.Br(),
                                html.H2("Choose a stock"),
                                 dropdown_stocks,
                                 html.Br()
                               ]
                             )
    ### This graph panel is filtered depending on the selected filters in the above defined dropdowns
    graph_panel = html.Div(id="timeseries-chart")

    html_content = html.Div(
                        dbc.Row([
                            dbc.Col(dropdown_panel,
                                    width=4,
                                    align='center'
                                    ),
                            dbc.Col(graph_panel,
                                    width=8,
                                    align='center'
                                    )
                                ],
                            justify='around'
                        )
    )

    heading = \
            dbc.Card(
                dbc.CardBody(
                    html.H1(html.B(title))
                ),
            )

    html_page = html.Div([
        heading,
        html.Br(),
        html_content
    ])

    return(html_page)

def timeseries_chart(timespan, stock_name):
    """
    Function, that displays the content of the graph_panel, which gets filtered by the selected
    dropdown elements (timespan, stock_name). Shows a linechart of the selected stock for the specified
    timespan.
    :param timespan: How many months into the past the data should range.
    :param stock_name: Name of stock, that should be displayed
    :return:
    """
    (orders, prices) = pl.prepare_orderAmounts_prices(df_orders)

    df_date_sorted = pl.filter_portfolio_date(orders, timespan)
    df_sorted = pl.filter_portfolio_stock(df_date_sorted, stock_name)

    df_timeseries = pl.prepare_timeseries(df_sorted, prices)

    return(dpl.plot_stock_linechart(df_timeseries))

########################################### CALLBACK FUNCTIONS #########################################################
# These callback functions need to be defined outside of the function, which uses it, because
# all callbacks need to be defined when the app is started!
@app.callback(Output('timeseries-chart', 'children'),
              [Input('dropdown-timespan', 'value'),
                Input('dropdown-stocks', 'value')
               ]
              )
def specify_dropdowns(timespan: int, stock_name: str):
    """
    Get the content element for the timeseries chart for the given dropdown selection.
    :param timespan: Amount of months into past, that should be visible in the plot
    :param stock_name: name of stock to show in the timeseries plot
    :return: html element of a timeseries plot
    """
    html_div = timeseries_chart(timespan, stock_name)
    return (html_div)


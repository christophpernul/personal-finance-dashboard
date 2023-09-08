from dash import html, dcc
import pandas as pd
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

### Import app (to define callbacks) and necessary preprocessed data
from dashboard.dashboard_lib.app import (
    app,
    df_orders,
    df_timeseries,
    df_expenses,
    df_incomes,
    portfolio_crypto_value,
)
from datahub.processing_layer import lib_data_operations as pl
from dashboard.plotting_lib import lib_dash_plot as dpl

theme_colors = {"background": "#32383E", "text": "#FFFFFF"}

piechart_descriptions = [
    {"values": "Percentage", "names": "Region", "title": "Region"},
    {"values": "Percentage", "names": "Type", "title": "Type"},
    {"values": "Percentage", "names": "Distributing", "title": "Distributing"},
    {
        "values": "Percentage",
        "names": "Replicationmethod",
        "title": "Replicationmethod",
    },
]


def html_expenses_tab(title="Expenses"):
    """
    Displays the tab with expenses data by using dropdowns to specify timespan and category:
    Top left: Title of the tab
    Top right: KPI panel with average expenses in given timeframe and for specified category
    Left: Dropdown elements for timespan and category
    Right: Barchart showing cashflow over time, updated by dropdowns including average expenses (same as KPI)
    :param title: Title of the tab
    :return: html element of the tab
    """
    #### Upper panel: 2 Dropdowns: timespan & category
    dropdown_timespan = dcc.Dropdown(
        options=[
            {"label": "3 Months", "value": 3},
            {"label": "6 Months", "value": 6},
            {"label": "1 Year", "value": 12},
            {"label": "2 Years", "value": 2 * 12},
            {"label": "3 Years", "value": 3 * 12},
            {"label": "4 Years", "value": 4 * 12},
            {"label": "5 Years", "value": 5 * 12},
            {"label": "Full", "value": -1},
        ],
        value=-1,
        id="dropdown-timespan",
    )
    category_default = "Overall"
    distinct_categories = sorted(list(df_expenses.columns))
    distinct_categories.append(category_default)

    dropdown_category = dcc.Dropdown(
        options=[
            {"label": category, "value": category}
            for category in distinct_categories
        ],
        value=category_default,
        id="dropdown-category",
    )
    dropdown_panel = html.Div(
        [
            html.H2("Choose a timeframe"),
            dropdown_timespan,
            html.Br(),
            html.H2("Choose a category"),
            dropdown_category,
            html.Br(),
        ]
    )

    distinct_months = sorted(list(set([idx for idx in df_expenses.index])))[
        ::-1
    ]
    month_default = distinct_months[0]

    ### Lower panel: Dropdown month
    dropdown_month = dcc.Dropdown(
        options=[
            {
                "label": str(timestamp.month_name())
                + " "
                + str(timestamp.year),
                "value": timestamp,
            }
            for timestamp in distinct_months
        ],
        value=month_default,
        id="dropdown-month",
    )
    dropdown_panel_month = html.Div(
        [html.H2("Choose a month"), dropdown_month]
    )
    ### This graph panel is filtered depending on the selected filters in the above defined dropdowns
    graph_panel = html.Div(id="main-barchart")
    html_average = html.H2(id="kpi-average")
    graph_panel_month = html.Div(id="barchart-month")

    upper_panel = html.Div(
        dbc.Row(
            [
                dbc.Col(dropdown_panel, width=4, align="center"),
                dbc.Col(graph_panel, width=8, align="center"),
            ],
            justify="around",
        )
    )

    lower_panel = html.Div(
        dbc.Row(
            [
                dbc.Col(dropdown_panel_month, width=4, align="center"),
                dbc.Col(graph_panel_month, width=8, align="center"),
            ],
            justify="around",
        )
    )

    heading = dbc.Col(
        dbc.Card(
            dbc.CardBody(html.H1(html.B(title))),
        ),
        width=6,
        align="center",
    )
    kpi_box = html.Div(
        dbc.Row(
            [dbc.Col(html.H2("Average Expenses")), dbc.Col(html_average)],
            justify="around",
        ),
    )
    kpi_panel = dbc.Col(
        dbc.Card(
            dbc.CardBody(html.Div([kpi_box])),
        ),
        width=6,
        align="center",
    )

    header_panel = dbc.Row([heading, kpi_panel], justify="around")

    html_page = html.Div(
        [
            header_panel,
            html.Br(),
            upper_panel,
            html.Hr(style={"color": "#FFFFFF", "border": "1px solid"}),
            lower_panel,
        ]
    )

    return html_page


def html_income_tab(title="Income"):
    """
    Displays the tab with income data by using dropdowns to specify timespan and category:
    Top left: Title of the tab
    Top right: KPI panel with average income in given timeframe and for specified category
    Left: Dropdown elements for timespan and category
    Right: Barchart showing income over time, updated by dropdowns including average income (same as KPI)
    :param title: Title of the tab
    :return: html element of the tab
    """

    dropdown_timespan = dcc.Dropdown(
        options=[
            {"label": "3 Months", "value": 3},
            {"label": "6 Months", "value": 6},
            {"label": "1 Year", "value": 12},
            {"label": "Full", "value": -1},
        ],
        value=-1,
        id="dropdown-timespan-income",
    )
    category_default = "Overall"
    distinct_categories = sorted(list(df_incomes.columns))
    distinct_categories.append(category_default)

    dropdown_category = dcc.Dropdown(
        options=[
            {"label": category, "value": category}
            for category in distinct_categories
        ],
        value=category_default,
        id="dropdown-category-income",
    )
    dropdown_panel = html.Div(
        [
            html.H2("Choose a timeframe"),
            dropdown_timespan,
            html.Br(),
            html.H2("Choose a category"),
            dropdown_category,
            html.Br(),
        ]
    )
    ### This graph panel is filtered depending on the selected filters in the above defined dropdowns
    graph_panel = html.Div(id="main-barchart-income")
    html_average = html.H2(id="kpi-average-income")

    html_content = html.Div(
        dbc.Row(
            [
                dbc.Col(dropdown_panel, width=4, align="center"),
                dbc.Col(graph_panel, width=8, align="center"),
            ],
            justify="around",
        )
    )

    heading = dbc.Col(
        dbc.Card(
            dbc.CardBody(html.H1(html.B(title))),
        ),
        width=6,
        align="center",
    )
    kpi_box = html.Div(
        dbc.Row(
            [dbc.Col(html.H2("Average Income")), dbc.Col(html_average)],
            justify="around",
        ),
    )
    kpi_panel = dbc.Col(
        dbc.Card(
            dbc.CardBody(html.Div([kpi_box])),
        ),
        width=6,
        align="center",
    )

    header_panel = dbc.Row([heading, kpi_panel], justify="around")

    html_page = html.Div([header_panel, html.Br(), html_content])

    return html_page


# def html_portfolio_overview(portfolio,
#                             group_columns: list,
#                             compute_columns: list,
#                             aggregation_columns: list,
#                             cost_column_name = "Investment",
#                             title = "Overview monthly Savings Plan",
#                             title_kpi_cost = "Monthly Investment",
#                             show_last_updated = False
#                             ):
#     """
#     Creates a HTML element that displays four elements as a page:
#     Top left: Title of page
#     Top right: Two KPI elements:
#                 Top:
#     Middle: Table with overview of current monthly savings plan
#     Bottom: Panel of four piecharts showing statistics about Region, Type, Replication method and accumulation
#     :param portfolio: dataframe holding transactions
#     :param group_columns: Columns used for groupby for piecharts
#     :param compute_columns: Columns that are aggregated by groupby
#     :param aggregation_columns: Aggregation function for groupby
#     :param title: Title of the page
#     :param title_kpi_cost: Title of the KPI element showing the total cost of investment
#     :param show_last_updated: Flag, whether the date of the last price update of the title_kpi_cost is shown
#     :return: HTML div element
#     """
#     ################################ Prepare data for remainder ########################################################
#     grouped_portfolio = pl.compute_percentage_per_group(portfolio,
#                                                         group_columns,
#                                                         compute_columns,
#                                                         aggregation_columns
#                                                         )
#
#     portfolio_view = portfolio.copy()
#     if show_last_updated == True:
#         assert len(set(portfolio_view["last_price_update"])) == 1, "Multiply dates for last price update in portfolio!"
#         last_updated = str(portfolio_view["last_price_update"].iloc[0]).split(" ")[0]
#         title_kpi_cost = title_kpi_cost + " (" + last_updated + ")"
#
#     portfolio_view["cost/a"] = 12*portfolio_view[cost_column_name]*portfolio_view["TER%"]/100
#     total_costs = round(portfolio_view[cost_column_name].sum(), 2)
#     average_TER = round((portfolio_view["cost/a"]/(12*total_costs)).sum()*100, 3)
#
#     portfolio_view = portfolio_view.drop(["cost/a"], axis=1)
#
#     all_group_columns = ["Name", "ISIN", "TER%"]+ group_columns
#     portfolio_view = portfolio_view.groupby(all_group_columns).sum()\
#                                     .reset_index().sort_values(cost_column_name, ascending=False)
#
#     portfolio_view = portfolio_view[all_group_columns + [cost_column_name]]
#
#
#
#     ################################ Define Dash App configuration ### #####################################################
#
#     heading = \
#         dbc.Col(
#             dbc.Card(
#                 dbc.CardBody(
#                     html.H1(html.B(title))
#                 ),
#             ),
#             width=6,
#             align='center'
#         )
#
#     kpi_panel_top = \
#                     html.Div(
#                         dbc.Row(
#                             [dbc.Col(html.H2("Average TER")),
#                              dbc.Col(html.H2(html.B(f"{average_TER} %")))],
#                             justify='around'
#                 ),
#             )
#
#     kpi_panel_bottom = \
#                     html.Div(
#                         dbc.Row(
#                             [dbc.Col(html.H2(title_kpi_cost)),
#                              dbc.Col(html.H2(html.B(f"{total_costs} €")))],
#                             justify='around'
#                 ),
#             )
#
#     kpi_panel = dbc.Col(
#         dbc.Card(
#             dbc.CardBody(
#                 html.Div([kpi_panel_top, kpi_panel_bottom])
#             ),
#         ),
#         width=6,
#         align='center'
#     )
#
#     header_panel = dbc.Row([heading,kpi_panel], justify='around')
#
#     dataframe_panel = \
#         dbc.Card(
#             dbc.CardBody(
#                 dpl.show_dataframe(portfolio_view, style_dict=theme_colors)
#             ),
#         )
#
#     chart_panel = dbc.Row([
#                             dbc.Col(dpl.show_piechart(grouped_portfolio[0],
#                                                       group_columns[0],
#                                                       "Percentage",
#                                                        theme_colors),
#                                     width=3,
#                                     align='center'),
#                             dbc.Col(dpl.show_piechart(grouped_portfolio[1],
#                                                       group_columns[1],
#                                                       "Percentage",
#                                                        theme_colors),
#                                     width=3,
#                                     align='center'),
#                             dbc.Col(dpl.show_piechart(grouped_portfolio[2],
#                                                       group_columns[2],
#                                                       "Percentage",
#                                                        theme_colors),
#                                     width=3,
#                                     align='center'),
#                             dbc.Col(dpl.show_piechart(grouped_portfolio[3],
#                                                       group_columns[3],
#                                                       "Percentage",
#                                                        theme_colors),
#                                     width=3,
#                                     align='center')
#                             ],
#         justify='around'
#     )
#
#
#
#     tab_overview = html.Div([header_panel,
#                              dataframe_panel,
#                              chart_panel
#                             ]
#                     )
#     return(tab_overview)
#
# def html_portfolio_timeseries(title="Portfolio Price Trend"):
#     """
#     Shows a panel of dropdown elements on the left hand side, where the user is able to filter the data
#     on a specific stock (also overall portfolio) and a timespan, which should be displayed.
#     On the right hand side a timeseries chart of the performance of the selected stock is shown during
#     the selected time span.
#     :param title: Title of the tab
#     :return: html element of the tab
#     """
#
#     dropdown_timespan = dcc.Dropdown(options=[
#                                         {"label": "1 Month", "value": 1},
#                                         {"label": "3 Months", "value": 3},
#                                         {"label": "6 Months", "value": 6},
#                                         {"label": "1 Year", "value": 12},
#                                         {"label": "5 Years", "value": 60},
#                                         {"label": "Full", "value": -1}
#                                     ],
#                                     value=-1,
#                                     id="dropdown-timespan",
#
#     )
#     stock_default = "Overall Portfolio"
#     distinct_stocks = list(df_orders["Name"].drop_duplicates().sort_values())
#     distinct_stocks.append(stock_default)
#
#     dropdown_stocks = dcc.Dropdown(options=[
#         {"label": stock_name, "value": stock_name} for stock_name in distinct_stocks
#     ],
#         value=stock_default,
#         id="dropdown-stocks"
#     )
#     dropdown_panel = html.Div([html.H2("Choose a timeframe"),
#                                 dropdown_timespan,
#                                  html.Br(),
#                                 html.H2("Choose a stock"),
#                                  dropdown_stocks,
#                                  html.Br()
#                                ]
#                              )
#     ### This graph panel is filtered depending on the selected filters in the above defined dropdowns
#     graph_panel = html.Div(id="timeseries-chart")
#
#     html_content = html.Div(
#                         dbc.Row([
#                             dbc.Col(dropdown_panel,
#                                     width=4,
#                                     align='center'
#                                     ),
#                             dbc.Col(graph_panel,
#                                     width=8,
#                                     align='center'
#                                     )
#                                 ],
#                             justify='around'
#                         )
#     )
#
#     heading = \
#             dbc.Card(
#                 dbc.CardBody(
#                     html.H1(html.B(title))
#                 ),
#             )
#
#     html_page = html.Div([
#         heading,
#         html.Br(),
#         html_content
#     ])
#
#     return(html_page)
#
# def timeseries_chart(timespan, stock_name):
#     """
#     Function, that displays the content of the graph_panel, which gets filtered by the selected
#     dropdown elements (timespan, stock_name). Shows a linechart of the selected stock for the specified
#     timespan.
#     :param timespan: How many months into the past the data should range.
#     :param stock_name: Name of stock, that should be displayed
#     :return: linechart HTML element
#     """
#     df_date_sorted = pl.filter_portfolio_date(df_timeseries, timespan)
#     df_sorted = pl.filter_portfolio_stock(df_date_sorted, stock_name)
#
#     return(dpl.plot_stock_linechart(df_sorted))
#
def barchart_expenses(timespan, category):
    """
    Displays the content of the main-barchart panel, after filtering by the selected dropdown elements
    (timespan, category). Shows a barchart of the selected expenses in the category for the specified timespan.
    :param timespan: How many months into the past the data should range.
    :param category: Category for which expenses are shown
    :return: barchart HTML element
    """
    df_date_sorted = pl.filter_portfolio_date(
        df_expenses.reset_index(), timespan
    ).set_index("date")
    if category == "Overall":
        df_sorted = pd.DataFrame(df_date_sorted.sum(axis=1)).rename(
            columns={0: "value"}
        )
    else:
        assert (
            category in df_expenses.columns
        ), "Category not in columns of dataframe!"
        df_sorted = df_date_sorted[[category]]
    return dpl.plot_barchart(df_sorted, "Expenses")


def barchart_month(month):
    """
    Displays the content of the barchart of expenses in the selected month.
    :param month: pd.Timestamp of last day of selected month in dropdown
    :return: barchart HTML element
    """
    df_month = (
        df_expenses.reset_index()[df_expenses.reset_index()["date"] == month]
        .set_index("date")
        .copy()
    )
    df_chart = (
        pd.DataFrame(df_month.stack())
        .rename_axis(index=["date", "tag"])
        .rename(columns={0: "value"})
        .reset_index()
        .drop(columns="date", axis=1)
        .set_index("tag")
    )
    return dpl.plot_barchart(df_chart, title="Expenses", x_axis="tag")


def barchart_income(timespan, category):
    """
    Displays the content of the main-barchart panel, after filtering by the selected dropdown elements
    (timespan, category). Shows a barchart of the selected income in the category for the specified timespan.
    :param timespan: How many months into the past the data should range.
    :param category: Category for which income is shown
    :return: barchart HTML element
    """
    df_date_sorted = pl.filter_portfolio_date(
        df_incomes.reset_index(), timespan
    ).set_index("date")
    if category == "Overall":
        df_sorted = pd.DataFrame(df_date_sorted.sum(axis=1)).rename(
            columns={0: "value"}
        )
    else:
        assert (
            category in df_incomes.columns
        ), "Category not in columns of dataframe!"
        df_sorted = df_date_sorted[[category]]
    return dpl.plot_barchart(df_sorted, "Income")


# def html_crypto_overview(title="Cryptocurrencies",
#                          title_kpi="Total Value"):
#     """
#     Shows a KPI element with the total crypto-portfolio value as well as a dropdown element.
#     By selecting a crypto-exchange (or "Overall" for the overall portfolio), a dataframe is displayed, that shows
#     all cryptocurrencies on that exchange with the current value in Euro.
#     :param title: Title of the tab
#     :param title_kpi: Title of the KPI element
#     :return: html element of the tab
#     """
#     ################################ Prepare data for remainder ########################################################
#     ### Prepare KPI content
#     from datetime import datetime
#     date_today = datetime.now().strftime(format="%Y-%m-%d %H:%M:%S")
#     title_kpi += " (" + date_today + ")"
#     total_value = portfolio_crypto_value[portfolio_crypto_value["exchange"] == "Overall"]["value"].sum()
#     value_show = str(round(total_value, 2)) + " €"
#
#     ################################ Define Dash App configuration #####################################################
#     heading = \
#         dbc.Col(
#             dbc.Card(
#                 dbc.CardBody(
#                     html.H1(html.B(title))
#                 ),
#             ),
#             width=6,
#             align='center'
#         )
#     kpi_box = \
#         html.Div(
#             dbc.Row(
#                 [dbc.Col(html.H2(title_kpi)),
#                  dbc.Col(html.H2(html.B(value_show)))],
#                 justify='around'
#             ),
#         )
#     kpi_panel = dbc.Col(
#         dbc.Card(
#             dbc.CardBody(
#                 html.Div([kpi_box])
#             ),
#         ),
#         width=6,
#         align='center'
#     )
#
#     header_panel = dbc.Row([heading, kpi_panel], justify='around')
#
#     ### Body panel
#     exchange_default = "Overall"
#     distinct_exchanges = sorted(list(portfolio_crypto_value["exchange"].drop_duplicates().sort_values()))
#
#     dropdown_exchange = dcc.Dropdown(options=[
#         {"label": exchange, "value": exchange} for exchange in distinct_exchanges
#     ],
#         value=exchange_default,
#         id="dropdown-crypto-exchange"
#     )
#     dropdown_panel = \
#     dbc.Card(
#         dbc.CardBody(
#             html.Div([html.H2("Choose an exchange"),
#                       dropdown_exchange,
#                       ]
#                      )
#         )
#     )
#
#     dataframe_panel = \
#         dbc.Card(
#             dbc.CardBody(
#                 html.Div(id="crypto-dataframe")
#             ),
#         )
#
#     tab_content = html.Div([header_panel,
#                             dropdown_panel,
#                             dataframe_panel
#                             ]
#                            )
#
#     return(tab_content)
#
#
# ########################################### CALLBACK FUNCTIONS #########################################################
# # These callback functions need to be defined outside of the function, which uses it, because
# # all callbacks need to be defined when the app is started!
# @app.callback(Output('timeseries-chart', 'children'),
#               [Input('dropdown-timespan', 'value'),
#                 Input('dropdown-stocks', 'value')
#                ]
#               )
# def dropdown_timeseries_chart(timespan: int, stock_name: str):
#     """
#     Get the content element for the timeseries chart for the given dropdown selection.
#     :param timespan: Amount of months into past, that should be visible in the plot
#     :param stock_name: name of stock to show in the timeseries plot
#     :return: html element of a timeseries plot
#     """
#     html_div = timeseries_chart(timespan, stock_name)
#     return (html_div)
#
@app.callback(
    Output("main-barchart", "children"),
    [Input("dropdown-timespan", "value"), Input("dropdown-category", "value")],
)
def dropdown_expenses_chart(timespan: int, category: str):
    """
    Get the content element for the timeseries chart for the given dropdown selection.
    :param timespan: Amount of months into past, that should be visible in the plot
    :param stock_name: name of stock to show in the timeseries plot
    :return: html element of a timeseries plot
    """
    html_div = barchart_expenses(timespan, category)
    return html_div


@app.callback(
    Output("kpi-average", "children"),
    [Input("dropdown-timespan", "value"), Input("dropdown-category", "value")],
)
def dropdown_expenses_average(timespan: int, category: str):
    """
    Get the content element for the timeseries chart for the given dropdown selection.
    :param timespan: Amount of months into past, that should be visible in the plot
    :param stock_name: name of stock to show in the timeseries plot
    :return: html element of a timeseries plot
    """
    df_date_sorted = pl.filter_portfolio_date(
        df_expenses.reset_index(), timespan
    ).set_index("date")
    if category == "Overall":
        df_sorted = df_date_sorted.sum(axis=1)
    else:
        assert (
            category in df_expenses.columns
        ), "Category not in columns of dataframe!"
        df_sorted = df_date_sorted[category]
    average = -df_sorted.mean()
    html_div = html.B(f"{average:.2f} €")
    return html_div


@app.callback(
    Output("barchart-month", "children"), Input("dropdown-month", "value")
)
def dropdown_month_barchart(month):
    """
    Get the content element for the barchart for the given dropdown selection (month).
    :param month: pd.Timestamp, timestamp of last day in selected month
    :return: html element of a timeseries plot
    """
    html_div = barchart_month(month)
    return html_div


@app.callback(
    Output("main-barchart-income", "children"),
    [
        Input("dropdown-timespan-income", "value"),
        Input("dropdown-category-income", "value"),
    ],
)
def dropdown_income_chart(timespan: int, category: str):
    """
    Get the content element for the timeseries chart for the given dropdown selection.
    :param timespan: Amount of months into past, that should be visible in the plot
    :param stock_name: name of stock to show in the timeseries plot
    :return: html element of a timeseries plot
    """
    html_div = barchart_income(timespan, category)
    return html_div


@app.callback(
    Output("kpi-average-income", "children"),
    [
        Input("dropdown-timespan-income", "value"),
        Input("dropdown-category-income", "value"),
    ],
)
def dropdown_income_average(timespan: int, category: str):
    """
    Get the content element for the timeseries chart for the given dropdown selection.
    :param timespan: Amount of months into past, that should be visible in the plot
    :param stock_name: name of stock to show in the timeseries plot
    :return: html element of a timeseries plot
    """
    df_date_sorted = pl.filter_portfolio_date(
        df_incomes.reset_index(), timespan
    ).set_index("date")
    if category == "Overall":
        df_sorted = df_date_sorted.sum(axis=1)
    else:
        assert (
            category in df_incomes.columns
        ), "Category not in columns of dataframe!"
        df_sorted = df_date_sorted[category]
    average = df_sorted.mean()
    html_div = html.B(f"{average:.2f} €")
    return html_div


# @app.callback(Output('crypto-dataframe', 'children'),
#               Input('dropdown-crypto-exchange', 'value'))
# def dropdown_crypto_exchange(exchange: str):
#     """
#     Render crypto-exchange dropdown to filter to dataframe, that should be displayed, for the overall portfolio
#     or a specfic exchange.
#     :param exchange: Name of exchange
#     :return: HTML element of the filtered dataframe to display
#     """
#     df_crypto_show = portfolio_crypto_value[portfolio_crypto_value["exchange"] == exchange]
#     df_crypto_show = df_crypto_show[["exchange", "currency", "name", "amount", "value"]]\
#                                     .sort_values("value",ascending=False)
#     return(dpl.show_dataframe(df_crypto_show, style_dict=theme_colors))

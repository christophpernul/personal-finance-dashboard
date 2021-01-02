import dash_html_components as html
import dash_bootstrap_components as dbc
import lib_data_operations as pl
import lib_dash_plot as dpl



theme_colors = {
    'background': '#32383E',
    'text': '#FFFFFF'
}

piechart_descriptions = [
    {'values': 'Percentage', 'names': 'Region', 'title': 'Region'},
    {'values': 'Percentage', 'names': 'Type', 'title': 'Type'},
    {'values': 'Percentage', 'names': 'Ausschüttung', 'title': 'Ausschüttung'},
    {'values': 'Percentage', 'names': 'Replikationsmethode', 'title': 'Replikationsmethode'}
]

def html_portfolio_overview(portfolio,
                            group_columns: list,
                            compute_columns: list,
                            aggregation_columns: list,
                            cost_column_name = "Betrag",
                            title = "Übersicht monatlicher Sparplan",
                            title_kpi_cost = "Monatliches Investment"
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
                            [dbc.Col(html.H2("Durchschnittliches TER")),
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
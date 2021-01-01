import dash_html_components as html
import dash_bootstrap_components as dbc
import lib_portfolio as pl
import lib_dash_plot as dpl



theme_colors = {
    'background': '#32383E',
    'text': '#FFFFFF'
}

piechart_descriptions = [
    {'values': 'Percentage', 'names': 'Region', 'title': 'Region'},
    {'values': 'Percentage', 'names': 'Type', 'title': 'Type'},
    {'values': 'Percentage', 'names': 'accumulating', 'title': 'Accumulating'},
    {'values': 'Percentage', 'names': 'physical', 'title': 'Physical'}
]

def html_portfolio_overview(portfolio):
    group_cols = ["Region", "Type", "accumulating", "physical"]
    compute_cols = ["Betrag", "Betrag", "Betrag", "Betrag"]
    agg_functions = ["sum", "sum", "sum", "sum"]
    grouped_portfolio = pl.compute_percentage_per_group(portfolio, group_cols, compute_cols, agg_functions)

    portfolio_view = portfolio.copy()
    portfolio_view["Betrag"] = -portfolio_view["Betrag"]
    portfolio_view["Kosten"] = -portfolio_view["Kosten"]

    portfolio_view["cost/a"] = 12*portfolio_view["Betrag"]*portfolio_view["TER in %"]/100
    total_monthly_savings = abs(portfolio_view["total_execution_cost"].iloc[0])
    average_TER = round((portfolio_view["cost/a"]/(12*total_monthly_savings)).sum()*100, 3)


    portfolio_view = portfolio_view[["Name", "ISIN", "Betrag", "Kosten", "Type", "Region", "physical", "accumulating", "TER in %"]]\
                    .sort_values("Betrag", ascending=False)



    ################################ Define Dash App configuration ### #####################################################

    heading = \
        dbc.Col(
            dbc.Card(
                dbc.CardBody(
                    html.H1(html.B("Übersicht monatlicher Sparplan"))
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
                            [dbc.Col(html.H2("Total monthly Savings")),
                             dbc.Col(html.H2(html.B(f"{total_monthly_savings} €")))],
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
                                                      group_cols[0],
                                                      "Percentage",
                                                       theme_colors),
                                    width=3,
                                    align='center'),
                            dbc.Col(dpl.show_piechart(grouped_portfolio[1],
                                                      group_cols[1],
                                                      "Percentage",
                                                       theme_colors),
                                    width=3,
                                    align='center'),
                            dbc.Col(dpl.show_piechart(grouped_portfolio[2],
                                                      group_cols[2],
                                                      "Percentage",
                                                       theme_colors),
                                    width=3,
                                    align='center'),
                            dbc.Col(dpl.show_piechart(grouped_portfolio[3],
                                                      group_cols[3],
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
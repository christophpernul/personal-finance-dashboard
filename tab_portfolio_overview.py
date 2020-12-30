import dash_html_components as html
import dash_bootstrap_components as dbc
import lib_portfolio as pl
import lib_dash_plot as dpl



colors = {
    'background': '#000000',
    'text': '#FFFFFF'
}
default_style_text = {'align': 'center',
                      'background': colors['background'],
                      'color': colors['text']
                      }

piechart_descriptions = [
    {'values': 'Percentage', 'names': 'Region', 'title': 'Region'},
    {'values': 'Percentage', 'names': 'Type', 'title': 'Type'},
    {'values': 'Percentage', 'names': 'accumulating', 'title': 'Accumulating'},
    {'values': 'Percentage', 'names': 'physical', 'title': 'Physical'}
]

def hmtl_overview(portfolio):
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
                    html.H1(html.B("Übersicht monatlicher Sparplan"), style=default_style_text)
                ),
            style=default_style_text
            ),
            width=6
        )

    kpi_panel_top = \
                    html.Div(
                        dbc.Row(
                            [dbc.Col(html.H2("Average TER", style=default_style_text)),
                             dbc.Col(html.H2(html.B(f"{average_TER} %"), style=default_style_text))],
                            justify='between'
                        # )
                    # )
                ),
                style=default_style_text
            )

    kpi_panel_bottom = \
                    html.Div(
                        dbc.Row(
                            [dbc.Col(html.H2("Total monthly Savings", style=default_style_text)),
                             dbc.Col(html.H2(html.B(f"{total_monthly_savings} €"), style=default_style_text))],
                            justify='between'
                        # )
                    # )
                ),
                style=default_style_text
            )

    kpi_panel = dbc.Col(
        dbc.Card(
            dbc.CardBody(
                html.Div([kpi_panel_top, kpi_panel_bottom], style=default_style_text)
            ),
        style=default_style_text
        ),
        width=6
    )

    header_panel = dbc.Row([heading,kpi_panel], justify='end')

    dataframe_panel = \
        dbc.Card(
            dbc.CardBody(
                dpl.show_dataframe(portfolio_view, style_dict=colors)
            ),
            style=default_style_text
        )

    chart_panel = dbc.Row([
                            dbc.Col(dpl.show_piechart(grouped_portfolio[0],
                                                      group_cols[0],
                                                      "Percentage",
                                                       piechart_descriptions[0]),
                                    width=3),
                            dbc.Col(dpl.show_piechart(grouped_portfolio[1],
                                                      group_cols[1],
                                                      "Percentage",
                                                       piechart_descriptions[1])
                                    , width=3),
                            dbc.Col(dpl.show_piechart(grouped_portfolio[2],
                                                      group_cols[2],
                                                      "Percentage",
                                                       piechart_descriptions[2])
                                    , width=3),
                            dbc.Col(dpl.show_piechart(grouped_portfolio[3],
                                                      group_cols[3],
                                                      "Percentage",
                                                       piechart_descriptions[3])
                                    , width=3)
                            ],
        justify='around'
    )



    tab_overview = html.Div([header_panel,
                             dataframe_panel,
                             chart_panel
                            ]
                    )
    return(tab_overview)
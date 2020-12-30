import dash
import dash_html_components as html
import dash_bootstrap_components as dbc
import dash_core_components as dcc
from dash.dependencies import Input, Output

import tab_portfolio_overview
import lib_portfolio as pl

colors = {
    'background': '#000000',
    'text': '#FFFFFF'
}
default_style_text = {'align': 'center',
                      'background': colors['background'],
                      'color': colors['text']
                      }
################################ Data Processing for ETF portfolio #####################################################
(df_etf_init, df_orders_init, _, _) = pl.load_data()
(df_orders, _) = pl.preprocess_orders(df_orders_init)
df_etf = pl.preprocess_etf_masterdata(df_etf_init)
orders_etf = pl.enrich_orders(df_orders, df_etf)
portfolio = pl.get_current_portfolio(orders_etf)

################################ Define Dash App configuration ### #####################################################
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.SLATE])
server = app.server

tab_nav_bar = dcc.Tabs(id="tab-navbar",
                       value="tab-expenses",
                       children=[
                                dcc.Tab(label="Ausgaben", value="tab-expenses", style=default_style_text),
                                dcc.Tab(label="Einnahmen", value="tab-income", style=default_style_text)
                                ],
                       style=default_style_text
                       )

body = html.Div(
    [tab_nav_bar,
     html.Div(id="tab-content", style=default_style_text)],
    style=default_style_text
)

app.layout = html.Div([body])

@app.callback(Output('tab-content', 'children'),
              Input('tab-navbar', 'value'))
def render_content(tab):
    if tab == "tab-expenses":
        return(tab_portfolio_overview.hmtl_overview(portfolio))
    elif tab == "tab-income":
        return(html.Div("Income", style=default_style_text))

if __name__ == '__main__':
    app.run_server(debug=True)
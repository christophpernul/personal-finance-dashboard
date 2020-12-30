import dash
import dash_html_components as html
import dash_bootstrap_components as dbc
import dash_core_components as dcc

colors = {
    'background': '#000000',
    'text': '#FFFFFF'
}
default_style_text = {'align': 'center',
                      'background': colors['background'],
                      'color': colors['text']
                      }

app = dash.Dash(__name__)#, external_stylesheets=[dbc.themes.SLATE])
server = app.server

tab_expenses = html.Div("Expenses")
tab_income = html.Div("Income")

tab_nav_bar = dcc.Tabs(id="all-tab-nav", value="tab-overview", children=[
    dcc.Tab(label="Ausgaben", id="tab-expenses", children=[tab_expenses]),
    dcc.Tab(label="Einnahmen", id="tab-income", children=[tab_income])
])

body = html.Div("Test")#, style=default_style_text)

app.layout = html.Div([tab_nav_bar])

if __name__ == '__main__':
    app.run_server(debug=True)
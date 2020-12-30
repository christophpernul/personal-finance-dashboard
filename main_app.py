import dash
import dash_html_components as html
import dash_bootstrap_components as dbc
import dash_core_components as dcc
from dash.dependencies import Input, Output

colors = {
    'background': '#000000',
    'text': '#FFFFFF'
}
default_style_text = {'align': 'center',
                      'background': colors['background'],
                      'color': colors['text']
                      }

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
        return(html.Div("Expenses", style=default_style_text))
    elif tab == "tab-income":
        return(html.Div("Income", style=default_style_text))

if __name__ == '__main__':
    app.run_server(debug=True)
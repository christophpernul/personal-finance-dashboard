"""
This is the central location, where the dash app is initiated. It is loaded in all necessary files
defining the app layouts from here, in order to use callbacks beside the main_app.py file. If this is
not structured this way the callbacks in subsequent files are not executed. (https://dash.plotly.com/urls)
See: https://community.plotly.com/t/dash-callback-in-a-separate-file/14122
"""
import dash
import dash_bootstrap_components as dbc

app = dash.Dash(__name__,
                title="Finance App",
                suppress_callback_exceptions=True,
                external_stylesheets=[dbc.themes.SLATE]
                )
server = app.server
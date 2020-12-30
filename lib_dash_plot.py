# import plotly.express as px
import plotly.graph_objects as go
import dash_table
import dash_core_components as dcc
import dash_html_components as html

def show_dataframe(df, style_dict={'background': '#000000', 'text':'#FFFFFF'}):
    """
    Function used to create a dash html <div> element showing a pd.DataFrame.
    :param df: pd.DataFrame for visualization
    :param style_dict: dictionary of custom styles of HTML element (default: black background, white text)
    :return: dash <div>> element with dataframe as table
    """
    return(html.Div(dash_table.DataTable(
                        id='table',
                        columns=[{"name": i, "id": i} for i in df.columns],
                        data=df.to_dict('records'),
                        style_cell={'textAlign': 'left',
                                    'background': style_dict['background'],
                                    'color': style_dict['text'],
                                    'padding-left': '10px'},
                        style_header={
                            'fontWeight': 'bold'
                        },
                        style_as_list_view=True
                )
            )
    )
def show_piechart(df, label_column, value_column, chart_description={'values':"columnValue",
                                                             'names': "columnGroup",
                                                             'title': 'Title'}):
    """
    Returns a dash html <div> element containing a piechart from data df
    :param df: holds data of piechart
    :param label_column: Column name of labels in df
    :param value_column: Column name of values in df
    :param chart_description: dictionary holding column names and title
    :return: dash <div> element with piechart
    """
    hoverinfo = str(label_column) + ": %{label}<br>" + str(value_column) + ": %{value}%" + "<extra></extra>"
    return(html.Div(dcc.Graph(figure = go.Figure(data=[go.Pie(labels=df[label_column],
                                                              values=df[value_column],
                                                              sort=False,
                                                              hovertemplate=hoverinfo)]
                                                 ).update_layout(paper_bgcolor='#000000',
                                                             font_color='#FFFFFF',
                                                             font_size=17,
                                                             title_font_size=22
                                                             )
                             )
                    )
           )
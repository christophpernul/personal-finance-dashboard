import plotly.graph_objects as go
import plotly.express as px

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
def show_piechart(df, label_column, value_column, theme_colors={'background':"#32383E",
                                                                'text': "#FFFFFF"}):
    """
    Returns a dash html <div> element containing a piechart from data df
    :param df: holds data of piechart
    :param label_column: Column name of labels in df
    :param value_column: Column name of values in df
    :param theme_colors: dictionary holding background and text colors
    :return: dash <div> element with piechart
    """
    hoverinfo = str(label_column) + ": %{label}<br>" + str(value_column) + ": %{value}%" + "<extra></extra>"
    fig = go.Figure(data=[go.Pie(labels=df[label_column],
                                 values=df[value_column],
                                 sort=False,
                                 hovertemplate=hoverinfo
                                 )
                          ]
                    )
    fig.update_layout(paper_bgcolor=theme_colors['background'],
                      font_color=theme_colors['text'],
                      font_size=17,
                      title_font_size=22,
                      title={'text': label_column[0].upper() + label_column[1:]
                             # upper() is used, because some columns are lowercase
                      }
                      )
    content = html.Div(
        dcc.Graph(
            figure=fig
        )
    )
    return(content)


def plot_stock_linechart(df_timeseries, theme_colors={'background': "#32383E", 'text': "#FFFFFF"}):
    """
    Uses a dataframe filtered on a specific stock and a given timespan to plot the timeseries of
    the stock-value and the total investment over time.
    :param df_timeseries: pd.DataFrame of price/investment values with Date filtered on a single stock/timespan
    :param theme_colors: dictionary, providing theme colors for the plot
    :return: html element consisting of a timeseries plot
    """
    try:
        fig = px.line(df_timeseries, x='Date', y=['Investment', 'Value'])
    except:
        ### In case the dataframe is empty, because there is no transaction in the specified timespan
        fig = go.Figure()
    fig.update_traces(mode="lines+markers")
    fig.update_layout(xaxis_title="Date",
                      yaxis_title="Value",
                      font_size=17,
                      legend=dict(x=0.01, y=0.99, title=""),
                      plot_bgcolor=theme_colors['background'],
                      paper_bgcolor = theme_colors['background'],
                      font_color = theme_colors['text'],
                      title_font_size = 22,
                      height=720
                      )
    content = html.Div(
        dcc.Graph(
            figure=fig
        )
    )
    return(content)

def plot_barchart(df, title, theme_colors={'background':"#32383E", 'text': "#FFFFFF"}):
    """
    Makes a barchart plot of the dataframe df, where x-axis is a date and y-axis is cashflow (expenses
    or incomes). Adds a horizontal line (average of specified time-interval) to the chart.
    :param df: pd.DataFrame, holding a Date column and another column with cashflow data
    :param title: Specify whether the chart shows Expenses or Income
    :return:
    """
    assert title in ["Expenses", "Income"], 'Title of barchart has to be in ["Expenses", "Income"]!'
    df_chart = df.reset_index().copy()
    ## Take first column: cannot specify name, because in case of overall displaying, the column has no name
    tag_column = df_chart.columns[1]
    df_chart = df_chart.rename(columns={tag_column: title})
    if title == "Expenses":
        df_chart[title] = df_chart[title]*-1
    average = df_chart[title].mean()
    try:
        fig = px.bar(df_chart, x='Date', y=title)
        fig.add_trace(go.Scatter(
            x = df_chart["Date"],
            y = [average for _ in range(len(df_chart))],
            mode="lines",
            line=dict(color='#1cbced'),
            name="Average"
        )
        )
        if title == "Expenses":
            fig.update_traces(marker_color="red")
        else:
            fig.update_traces(marker_color="green")
    except:
        ### In case the dataframe is empty, because there is no transaction in the specified timespan
        fig = go.Figure()
    fig.update_layout(plot_bgcolor=theme_colors['background'],
                      paper_bgcolor=theme_colors['background'],
                      font_color=theme_colors['text'],
                      font_size=17,
                      hoverlabel=dict(font=dict(color='black'))
                      )
    content = html.Div(
        dcc.Graph(
            figure=fig
        )
    )
    return(content)
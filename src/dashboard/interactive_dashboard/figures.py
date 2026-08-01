"""Plotly figure builders for the dashboard.

Every figure is styled with the shared dark theme from :mod:`config`.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from . import config
from .data import FinanceData

C = config.COLORS


def _base_layout(fig: go.Figure, *, height: int | None = None) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=C["text"]),
        margin=dict(l=60, r=20, t=40, b=40),
        hovermode="x unified",
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    if height is not None:
        fig.update_layout(height=height)
    fig.update_xaxes(gridcolor=C["grid"], zerolinecolor=C["grid"])
    fig.update_yaxes(gridcolor=C["grid"], zerolinecolor=C["grid"])
    return fig


def _empty(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font=dict(color=C["text_muted"], size=16),
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
    )
    return _base_layout(fig, height=300)


def monthly_bar_figure(
    data: FinanceData, kind: str, selected_month: pd.Timestamp | None = None
) -> go.Figure:
    """Monthly totals as bars, with a dashed average reference line.

    For ``kind == 'cashflow'`` bars are colored by sign; the clicked/selected
    month is highlighted.
    """
    series = data.totals(kind)
    if series.empty:
        return _empty("No data in the selected period")

    months = series.index
    values = series.values
    avg = float(series.mean())

    if kind == "cashflow":
        colors = [C["positive"] if v >= 0 else C["negative"] for v in values]
        bar_name = "Net cashflow"
    else:
        base = C["expense"] if kind == "expenses" else C["income"]
        colors = [base] * len(values)
        bar_name = "Expenses" if kind == "expenses" else "Income"

    # Highlight the selected month.
    if selected_month is not None and selected_month in months:
        colors = list(colors)
        colors[list(months).index(selected_month)] = C["selected"]

    fig = go.Figure()
    fig.add_bar(
        x=months,
        y=values,
        marker_color=colors,
        name=bar_name,
        hovertemplate="%{x|%b %Y}<br>%{y:,.0f} €<extra></extra>",
    )
    fig.add_hline(
        y=avg,
        line=dict(color=C["average"], width=2, dash="dash"),
        annotation_text=f"Average {avg:,.0f} €",
        annotation_position="top left",
        annotation_font_color=C["average"],
    )
    _base_layout(fig, height=420)
    fig.update_layout(showlegend=False)
    fig.update_yaxes(title_text="€")
    fig.update_xaxes(title_text="Month")
    return fig


def category_breakdown_figure(
    data: FinanceData, kind: str, month: pd.Timestamp | None
) -> go.Figure:
    """Horizontal bar chart of a single month's per-category amounts."""
    if month is None:
        return _empty("Click a month to see its category breakdown")
    breakdown = data.category_breakdown(kind, month)
    if breakdown.empty:
        return _empty(f"No {kind} recorded in {month:%b %Y}")

    # Ascending so the largest category is on top of a horizontal bar chart.
    breakdown = breakdown.sort_values(ascending=True)
    fig = go.Figure()
    fig.add_bar(
        x=breakdown.values,
        y=breakdown.index,
        orientation="h",
        marker_color=config.CATEGORY_PALETTE[: len(breakdown)][::-1],
        hovertemplate="%{y}<br>%{x:,.0f} €<extra></extra>",
    )
    _base_layout(fig, height=420)
    fig.update_layout(
        title=dict(text=f"{month:%B %Y} by category", font=dict(size=15)),
        showlegend=False,
    )
    fig.update_xaxes(title_text="€")
    return fig


def category_average_figure(data: FinanceData, kind: str) -> go.Figure:
    """Horizontal bar chart of average monthly amount per category over the period."""
    avg = data.category_average(kind)
    if avg.empty:
        return _empty("No data in the selected period")

    avg = avg.sort_values(ascending=True)
    fig = go.Figure()
    fig.add_bar(
        x=avg.values,
        y=avg.index,
        orientation="h",
        marker_color=config.CATEGORY_PALETTE[: len(avg)][::-1],
        hovertemplate="%{y}<br>avg %{x:,.0f} €/month<extra></extra>",
    )
    _base_layout(fig, height=420)
    fig.update_layout(
        title=dict(
            text="Average per category (selected period)", font=dict(size=15)
        ),
        showlegend=False,
    )
    fig.update_xaxes(title_text="€ / month")
    return fig

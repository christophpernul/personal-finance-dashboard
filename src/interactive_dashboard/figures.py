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


def _make_room_for_labels(fig: go.Figure, values) -> None:
    """Extend the x-axis of a horizontal bar chart so outside end-labels fit."""
    if len(values) == 0:
        return
    top = float(max(values))
    if top <= 0:
        return
    fig.update_xaxes(range=[0, top * 1.18])
    fig.update_layout(margin=dict(l=60, r=40, t=40, b=40))


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


def _category_bar_figure(
    values: pd.Series, *, title: str, x_title: str, hover_suffix: str
) -> go.Figure:
    """Horizontal bars, one per category, largest on top, labelled at the end."""
    # Ascending so the largest category is on top of a horizontal bar chart.
    values = values.sort_values(ascending=True)
    fig = go.Figure()
    fig.add_bar(
        x=values.values,
        y=values.index,
        orientation="h",
        marker_color=[config.category_color(c) for c in values.index],
        text=[f"{v:,.0f} €" for v in values.values],
        textposition="outside",
        textfont=dict(color=C["text"]),
        cliponaxis=False,
        hovertemplate="%{y}<br>" + hover_suffix + "<extra></extra>",
    )
    _base_layout(fig, height=420)
    _make_room_for_labels(fig, values.values)
    fig.update_layout(
        title=dict(text=title, font=dict(size=15)), showlegend=False
    )
    fig.update_xaxes(title_text=x_title)
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
    return _category_bar_figure(
        breakdown,
        title=f"{month:%B %Y} by category",
        x_title="€",
        hover_suffix="%{x:,.0f} €",
    )


def category_average_figure(data: FinanceData, kind: str) -> go.Figure:
    """Horizontal bar chart of average monthly amount per category over the period."""
    avg = data.category_average(kind)
    if avg.empty:
        return _empty("No data in the selected period")
    return _category_bar_figure(
        avg,
        title="Average per category (selected period)",
        x_title="€ / month",
        hover_suffix="avg %{x:,.0f} €/month",
    )


# ---------------------------------------------------------------------------
# Yearly tab
# ---------------------------------------------------------------------------
def yearly_totals_figure(
    totals: pd.DataFrame, partial_year: int | None = None
) -> go.Figure:
    """Income, expenses and net cashflow per calendar year as grouped bars.

    ``partial_year`` marks a year that is still running: its bars are hatched
    and its tick reads "<year> YTD".
    """
    if totals.empty:
        return _empty("No data available")

    labels = [
        f"{y} YTD" if y == partial_year else str(y) for y in totals.index
    ]
    hatch = ["/" if y == partial_year else "" for y in totals.index]
    series = [
        ("total_income", "Income", C["income"]),
        ("total_expense", "Expenses", C["expense"]),
        ("net", "Cashflow", C["net"]),
    ]
    fig = go.Figure()
    for column, name, color in series:
        fig.add_bar(
            x=labels,
            y=totals[column].values,
            name=name,
            marker=dict(
                color=color,
                pattern=dict(shape=hatch, fgcolor=C["panel"], size=6),
            ),
            text=[f"{v / 1000:,.1f}k" for v in totals[column].values],
            textposition="outside",
            textfont=dict(color=C["text"], size=11),
            cliponaxis=False,
            hovertemplate="%{y:,.0f} €",
        )
    _base_layout(fig, height=460)
    fig.update_layout(
        barmode="group",
        bargap=0.22,
        bargroupgap=0.06,
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
    )
    fig.update_xaxes(type="category")
    fig.update_yaxes(title_text="€")
    return fig


def category_comparison_figure(
    current: pd.Series,
    past: pd.Series,
    current_label: str,
    past_label: str,
    kind: str,
) -> go.Figure:
    """Per-category amounts of one year next to those of a baseline year."""
    both = pd.DataFrame({"current": current, "past": past}).fillna(0.0)
    if both.empty:
        return _empty(f"No {kind} to compare")

    # Ascending so the largest current category ends up on top.
    both = both.sort_values(["current", "past"], ascending=True)
    color = C["expense"] if kind == "expenses" else C["income"]
    fig = go.Figure()
    # Within a group plotly draws traces bottom-up: past first, current on top.
    for column, name, bar_color in (
        ("past", past_label, C["reference"]),
        ("current", current_label, color),
    ):
        fig.add_bar(
            x=both[column].values,
            y=both.index,
            orientation="h",
            name=name,
            marker_color=bar_color,
            text=[f"{v:,.0f} €" for v in both[column].values],
            textposition="outside",
            textfont=dict(color=C["text"], size=11),
            cliponaxis=False,
            hovertemplate="%{x:,.0f} €",
        )
    _base_layout(fig, height=_comparison_height(len(both)))
    _make_room_for_labels(fig, both.to_numpy().ravel())
    fig.update_layout(
        barmode="group",
        bargap=0.25,
        hovermode="y unified",
        title=dict(
            text=f"{kind.capitalize()} by category", font=dict(size=15)
        ),
        legend=dict(
            orientation="h",
            y=1.0,
            yanchor="bottom",
            x=1,
            xanchor="right",
            traceorder="reversed",
        ),
    )
    fig.update_xaxes(title_text="€")
    return fig


def category_delta_figure(
    current: pd.Series, past: pd.Series, past_label: str, kind: str
) -> go.Figure:
    """Change per category (current - past), biggest increase on top.

    Bars are colored by whether the change is good or bad for the wallet: more
    spending / less income is negative.
    """
    both = pd.DataFrame({"current": current, "past": past}).fillna(0.0)
    delta = (both["current"] - both["past"]).round(2)
    delta = delta[delta != 0].sort_values(ascending=True)
    if delta.empty:
        return _empty("No difference between the two periods")

    more_is_good = kind == "income"
    colors = [
        C["positive"] if (v > 0) == more_is_good else C["negative"]
        for v in delta.values
    ]
    fig = go.Figure()
    fig.add_bar(
        x=delta.values,
        y=delta.index,
        orientation="h",
        marker_color=colors,
        text=[f"{v:+,.0f} €" for v in delta.values],
        textposition="outside",
        textfont=dict(color=C["text"], size=11),
        cliponaxis=False,
        hovertemplate="%{y}<br>%{x:+,.0f} €<extra></extra>",
    )
    # Same height as the comparison chart it sits next to.
    _base_layout(fig, height=_comparison_height(len(both)))
    # Pad both ends so the outside labels of the longest bars fit.
    lo, hi = min(delta.min(), 0.0), max(delta.max(), 0.0)
    pad = (hi - lo) * 0.2
    fig.update_xaxes(range=[lo - pad, hi + pad], title_text="€")
    fig.update_layout(
        title=dict(text=f"Change vs. {past_label}", font=dict(size=15)),
        showlegend=False,
    )
    return fig


def _comparison_height(n_categories: int) -> int:
    return max(420, 34 * n_categories + 130)

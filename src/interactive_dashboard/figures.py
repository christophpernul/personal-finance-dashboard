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


def cash_liquidity_figure(liquidity: pd.DataFrame) -> go.Figure:
    """Stacked monthly bars of available (accounts) and bound (fixed-term
    deposits) cash, with liabilities below zero once anything is owed; the
    projected months after the current one are faded."""
    if liquidity.empty:
        return _empty("No cash balances recorded yet")
    # The dates are month ends; label the bars by month on a category axis so
    # they don't sit on the next month's tick.
    months = [d.strftime("%b %Y") for d in liquidity.index]
    projected = liquidity["is_projection"].tolist()
    opacity = [0.45 if p else 1.0 for p in projected]

    series = [
        ("available", "Available", C["cash_available"]),
        ("bound", "Bound (fixed-term)", C["cash_bound"]),
    ]
    if liquidity["liabilities"].fillna(0.0).ne(0).any():
        series.append(("liabilities", "Liabilities", C["negative"]))

    fig = go.Figure()
    for column, name, color in series:
        fig.add_bar(
            x=months,
            y=liquidity[column].fillna(0.0),
            name=name,
            marker=dict(color=color, opacity=opacity),
            hovertemplate=f"{name}: %{{y:,.0f}} €<extra></extra>",
        )
    if any(projected):
        fig.add_vrect(
            x0=projected.index(True) - 0.5,
            x1=len(months) - 0.5,
            fillcolor=C["grid"],
            opacity=0.15,
            line_width=0,
            annotation_text="Projection: balances unchanged, deposits paid out",
            annotation_position="top left",
            annotation_font_color=C["text_muted"],
        )
    _base_layout(fig, height=400)
    fig.update_layout(
        # relative: negative liabilities stack downwards from zero
        barmode="relative",
        legend=dict(orientation="h", y=1.18, x=0, bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=60, r=20, t=80, b=40),
    )
    fig.update_xaxes(type="category")
    fig.update_yaxes(title_text="€")
    return fig


def term_deposit_timeline_figure(
    deposits: pd.DataFrame, today: pd.Timestamp
) -> go.Figure:
    """One horizontal bar per running/upcoming fixed-term deposit from its
    start to its end date, with a line at today."""
    if deposits.empty:
        return _empty("No running fixed-term deposits")
    deposits = deposits.sort_values("end_date", ascending=False)
    labels = [
        f"{row.bank}  ·  {row.principal:,.0f} €"
        for row in deposits.itertuples()
    ]
    duration_ms = (
        deposits["end_date"] - deposits["start_date"]
    ).dt.total_seconds() * 1000
    texts = [
        f"{row.rate_pa * 100:.2f} %  ·  until {row.end_date:%d %b %Y}"
        for row in deposits.itertuples()
    ]

    fig = go.Figure()
    fig.add_bar(
        y=labels,
        x=duration_ms,
        base=deposits["start_date"],
        orientation="h",
        marker_color=C["cash_bound"],
        text=texts,
        textposition="inside",
        insidetextanchor="end",
        textfont=dict(color="#ffffff", size=12),
        customdata=deposits[["start_date", "end_date"]],
        hovertemplate=(
            "%{y}<br>%{customdata[0]|%d %b %Y} – %{customdata[1]|%d %b %Y}"
            "<extra></extra>"
        ),
    )
    fig.add_shape(
        type="line",
        x0=today,
        x1=today,
        y0=0,
        y1=1,
        yref="paper",
        line=dict(color=C["selected"], width=2, dash="dash"),
    )
    fig.add_annotation(
        x=today,
        y=1,
        yref="paper",
        yanchor="bottom",
        text="Today",
        showarrow=False,
        font=dict(color=C["selected"]),
    )
    _base_layout(fig, height=max(200, 70 * len(deposits) + 100))
    fig.update_layout(showlegend=False, hovermode="closest", bargap=0.35)
    fig.update_xaxes(type="date")
    return fig


# Allocation buckets: the attribute's own values get distinct hues (in display
# order), buckets of asset classes the attribute doesn't apply to stay grey so
# they read as "not part of this split", and "Unknown" (master data missing)
# is darker still.
ALLOCATION_PALETTE = [
    "#29b6f6",
    "#2ec4b6",
    "#a78bfa",
    "#f1c40f",
    "#e67e22",
    "#e84393",
    "#8d6e63",
]
ALLOCATION_OTHER = ["#95a5a6", "#7f8c8d", "#b2babb", "#6c7a89", "#a4b0be"]
ALLOCATION_UNKNOWN = "#566573"


def allocation_colors(own: list[str], others: list[str]) -> dict[str, str]:
    """Fixed color per bucket label of one breakdown."""
    colors = {
        b: ALLOCATION_PALETTE[i % len(ALLOCATION_PALETTE)]
        for i, b in enumerate(own)
    }
    colors.update(
        {
            b: ALLOCATION_OTHER[i % len(ALLOCATION_OTHER)]
            for i, b in enumerate(others)
        }
    )
    colors["Unknown"] = ALLOCATION_UNKNOWN
    return colors


def allocation_donut_figure(
    breakdown: pd.DataFrame, colors: dict[str, str]
) -> go.Figure:
    """Share of value per bucket as a donut; hover lists the holdings."""
    if breakdown.empty:
        return _empty("No holdings selected")

    def _names(names: list[str]) -> str:
        shown = "<br>".join(names[:8])
        more = len(names) - 8
        return shown + (f"<br>… and {more} more" if more > 0 else "")

    fig = go.Figure(
        go.Pie(
            labels=breakdown["bucket"],
            values=breakdown["value"],
            hole=0.55,
            sort=False,
            direction="clockwise",
            marker=dict(
                colors=[
                    colors.get(b, ALLOCATION_UNKNOWN)
                    for b in breakdown["bucket"]
                ],
                line=dict(color=C["panel"], width=2),
            ),
            textinfo="percent",
            textposition="inside",
            insidetextorientation="horizontal",
            customdata=list(
                zip(breakdown["n"], [_names(n) for n in breakdown["names"]])
            ),
            hovertemplate=(
                "<b>%{label}</b><br>%{value:,.0f} €  ·  %{percent}"
                "<br>%{customdata[0]} holdings<br><br>%{customdata[1]}"
                "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=C["text"]),
        margin=dict(l=10, r=10, t=10, b=10),
        height=240,
        showlegend=False,
        uniformtext=dict(minsize=10, mode="hide"),
    )
    return fig


# ---------------------------------------------------------------------------
# Earnings (dividends and interest)
# ---------------------------------------------------------------------------
def _short(name: str, limit: int = 42) -> str:
    return name if len(name) <= limit else name[: limit - 1].rstrip() + "…"


def earnings_yearly_figure(
    earnings,
    years: list[int],
    stack_by: str = "type",
    selected_year: int | None = None,
) -> go.Figure:
    """Earnings per year as stacked bars, by type or by holding.

    The running year is hatched and reads "<year> YTD"; the other years than
    ``selected_year`` are dimmed so the clicked bar stands out.
    """
    if not years:
        return _empty("No earnings in the selected years")
    current = earnings.current_year
    if stack_by == "holding":
        matrix = earnings.yearly_by_holding().loc[years]
        holdings = earnings.holdings()
        series = [
            (
                h,
                holdings.at[h, "name"],
                holdings.at[h, "type"],
                earnings.holding_colors.get(h, C["text_muted"]),
            )
            for h in matrix.columns
        ]
    else:
        from .earnings import TYPE_COLORS

        matrix = earnings.yearly_by_type().loc[years]
        series = [
            (t, t, t, TYPE_COLORS.get(t, C["text_muted"]))
            for t in matrix.columns
        ]

    labels = [f"{y} YTD" if y == current else str(y) for y in years]
    hatch = ["/" if y == current else "" for y in years]
    opacity = [
        1.0 if selected_year is None or y == selected_year else 0.45
        for y in years
    ]
    fig = go.Figure()
    for key, name, type_, color in series:
        values = matrix[key].values
        if not (values > 0).any():
            continue
        fig.add_bar(
            x=labels,
            y=values,
            name=_short(name, 34),
            legendgroup=type_,
            customdata=[[name, type_, y] for y in years],
            marker=dict(
                color=color,
                opacity=opacity,
                pattern=dict(shape=hatch, fgcolor=C["panel"], size=6),
                line=dict(width=0),
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
                "%{x}: %{y:,.2f} €<extra></extra>"
            )
            if stack_by == "holding"
            else "%{y:,.2f} €",
        )
    totals = matrix.sum(axis=1).values
    fig.add_scatter(
        x=labels,
        y=totals,
        mode="text",
        text=[f"{v:,.0f} €" for v in totals],
        textposition="top center",
        textfont=dict(color=C["text"], size=12),
        showlegend=False,
        hoverinfo="skip",
        cliponaxis=False,
    )
    _base_layout(fig, height=460)
    fig.update_layout(
        barmode="stack",
        bargap=0.3,
        hovermode="closest" if stack_by == "holding" else "x unified",
        showlegend=stack_by != "holding",
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
        clickmode="event",
    )
    fig.update_xaxes(type="category")
    top = float(totals.max()) if len(totals) else 0.0
    fig.update_yaxes(title_text="€", range=[0, top * 1.12 if top > 0 else 1])
    return fig


def earnings_holdings_figure(
    rows: pd.DataFrame,
    colors: dict[str, str],
    *,
    title: str,
    empty_message: str,
    previous: pd.Series | None = None,
) -> go.Figure:
    """Horizontal bars per holding (``rows``: holding, name, type, amount,
    payments), largest on top, labelled with the amount. ``previous`` (holding
    -> amount) adds last year's amount to the hover."""
    if rows.empty:
        return _empty(empty_message)
    rows = rows.iloc[::-1]  # largest on top
    prev = (
        rows["holding"].map(previous).fillna(0.0)
        if previous is not None
        else pd.Series(float("nan"), index=rows.index)
    )
    custom = list(
        zip(rows["name"], rows["type"], rows["payments"], prev.values)
    )
    hover = (
        "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
        "%{x:,.2f} € from %{customdata[2]} payment(s)"
    )
    if previous is not None:
        hover += "<br>Previous year: %{customdata[3]:,.2f} €"
    fig = go.Figure()
    fig.add_bar(
        x=rows["amount"].values,
        y=[_short(n) for n in rows["name"]],
        orientation="h",
        marker_color=[colors.get(h, C["text_muted"]) for h in rows["holding"]],
        customdata=custom,
        text=[f"{v:,.2f} €" for v in rows["amount"].values],
        textposition="outside",
        textfont=dict(color=C["text"]),
        cliponaxis=False,
        hovertemplate=hover + "<extra></extra>",
    )
    _base_layout(fig, height=max(300, 110 + 30 * len(rows)))
    _make_room_for_labels(fig, rows["amount"].values)
    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        showlegend=False,
        hovermode="closest",
        margin=dict(l=20, r=40, t=50, b=40),
    )
    fig.update_yaxes(automargin=True)
    fig.update_xaxes(title_text="€")
    return fig

"""Interactive personal-finance dashboard (Plotly Dash).

Tabs: Expenses, Income, Cashflow. Each tab lets you freely pick a month range
(slider + presets), shows monthly bars with the period average, and — for
Expenses/Income — drills into per-category spend when you click a month, plus the
average spend per category over the selected period.

The Yearly tab aggregates per calendar year: income/expenses/cashflow totals
(full year or year-to-date) and a per-category comparison of the expenses of
any two years.

Run with::

    python -m src.interactive_dashboard.app
"""
from __future__ import annotations

import pandas as pd
from dash import (
    Dash,
    Input,
    Output,
    State,
    callback_context,
    dash_table,
    dcc,
    html,
)
from dash.dash_table.Format import Format, Group, Scheme, Symbol

from . import config, figures
from .data import FinanceData, load_finance_data
from .portfolio import PortfolioData, load_portfolio_data

C = config.COLORS

# --- Load data once at startup ----------------------------------------------
DATA: FinanceData = load_finance_data()
MONTHS: list[pd.Timestamp] = DATA.months
N_MONTHS = len(MONTHS)

# Year-to-date views run up to the end of last month (the running month is
# incomplete). The year that day falls in is the "current" one; it only counts
# as a complete year while the cutoff sits on Dec 31, i.e. during January.
YTD_CUTOFF: pd.Timestamp = DATA.ytd_cutoff
CURRENT_YEAR = YTD_CUTOFF.year
PAST_YEARS: list[int] = [y for y in DATA.years if y < CURRENT_YEAR]
YEAR_COMPLETE = YTD_CUTOFF.month == 12
YTD_SPAN = "Jan" if YTD_CUTOFF.month == 1 else f"Jan – {YTD_CUTOFF:%b}"

PORTFOLIO: PortfolioData = load_portfolio_data()

# Tab registry — add a dict here to introduce a new tab later.
# ``layout`` selects how the tab is rendered: "series" = monthly bars + range
# slider; "yearly" = calendar-year totals + category comparisons;
# "portfolio" = positions table + aggregate KPI cards.
TABS = [
    {
        "kind": "expenses",
        "label": "Expenses",
        "layout": "series",
        "has_categories": True,
    },
    {
        "kind": "income",
        "label": "Income",
        "layout": "series",
        "has_categories": True,
    },
    {
        "kind": "cashflow",
        "label": "Cashflow",
        "layout": "series",
        "has_categories": False,
    },
    {"kind": "yearly", "label": "Yearly", "layout": "yearly"},
    {"kind": "portfolio", "label": "Portfolio", "layout": "portfolio"},
]
KINDS = [t["kind"] for t in TABS]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _month_label(ts: pd.Timestamp) -> str:
    return ts.strftime("%b %Y")


def _slider_marks() -> dict:
    """Show the year at each January tick."""
    marks = {}
    for i, m in enumerate(MONTHS):
        if m.month == 1 or i == 0 or i == N_MONTHS - 1:
            marks[i] = {
                "label": str(m.year),
                "style": {"color": C["text_muted"]},
            }
    return marks


def _preset_range(preset: str) -> list[int]:
    """Return [start_idx, end_idx] for a named preset."""
    last = N_MONTHS - 1
    if preset == "year":
        max_year = MONTHS[-1].year
        idx = [i for i, m in enumerate(MONTHS) if m.year == max_year]
        return [idx[0], idx[-1]]
    if preset == "m12":
        return [max(0, N_MONTHS - 12), last]
    if preset == "m6":
        return [max(0, N_MONTHS - 6), last]
    return [0, last]  # full


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def _card(children, **style) -> html.Div:
    base = {
        "backgroundColor": C["panel"],
        "borderRadius": "10px",
        "padding": "18px 22px",
        "margin": "10px",
    }
    base.update(style)
    return html.Div(children, style=base)


def _kpi(label_id: str, value_id: str, label_text: str) -> html.Div:
    return _card(
        [
            html.Div(
                label_text,
                id=label_id,
                style={"color": C["text_muted"], "fontSize": "15px"},
            ),
            html.Div(
                "—",
                id=value_id,
                style={
                    "color": C["text"],
                    "fontSize": "30px",
                    "fontWeight": "600",
                    "marginTop": "4px",
                },
            ),
        ],
        flex="1",
        minWidth="200px",
    )


def _txn_card(kind: str) -> html.Div:
    """Table listing individual transactions for a clicked category."""
    return _card(
        [
            html.Div(
                "Click a category bar above to list its transactions",
                id=f"{kind}-txn-title",
                style={
                    "color": C["text"],
                    "fontSize": "15px",
                    "fontWeight": "600",
                    "marginBottom": "10px",
                },
            ),
            dash_table.DataTable(
                id=f"{kind}-txn-table",
                columns=[
                    {"name": "Date", "id": "date"},
                    {"name": "Tag", "id": "tag"},
                    {
                        "name": "Amount",
                        "id": "amount",
                        "type": "numeric",
                        "format": _MONEY,
                    },
                ],
                data=[],
                sort_action="native",
                page_size=15,
                style_as_list_view=True,
                style_table={"overflowX": "auto"},
                style_header={
                    "backgroundColor": C["background"],
                    "color": C["text"],
                    "fontWeight": "600",
                    "border": "none",
                    "borderBottom": f"2px solid {C['grid']}",
                },
                style_cell={
                    "backgroundColor": C["panel"],
                    "color": C["text"],
                    "border": "none",
                    "borderBottom": f"1px solid {C['grid']}",
                    "padding": "8px 10px",
                    "fontFamily": "Segoe UI, Arial, sans-serif",
                    "fontSize": "13px",
                    "textAlign": "right",
                },
                style_cell_conditional=[
                    {"if": {"column_id": c}, "textAlign": "left"}
                    for c in ("date", "tag")
                ],
            ),
        ],
    )


def _preset_button(kind: str, preset: str, text: str) -> html.Button:
    return html.Button(
        text,
        id=f"{kind}-preset-{preset}",
        n_clicks=0,
        style={
            "backgroundColor": C["background"],
            "color": C["text"],
            "border": f"1px solid {C['grid']}",
            "borderRadius": "6px",
            "padding": "6px 14px",
            "margin": "0 6px 0 0",
            "cursor": "pointer",
        },
    )


def _tab_shell(label: str, kind: str, body: list) -> dcc.Tab:
    return dcc.Tab(
        label=label,
        value=kind,
        children=html.Div(body, style={"padding": "6px"}),
        style={
            "backgroundColor": C["background"],
            "color": C["text_muted"],
            "borderTop": f"1px solid {C['grid']}",
            "borderRight": f"1px solid {C['grid']}",
            "borderBottom": f"1px solid {C['grid']}",
            "borderLeft": f"1px solid {C['grid']}",
        },
        selected_style={
            "backgroundColor": C["panel"],
            "color": C["text"],
            "borderTop": f"3px solid {C['average']}",
            "borderRight": f"1px solid {C['grid']}",
            "borderBottom": f"1px solid {C['grid']}",
            "borderLeft": f"1px solid {C['grid']}",
        },
    )


def build_tab(tab: dict) -> dcc.Tab:
    if tab["layout"] == "portfolio":
        return build_portfolio_tab(tab)
    if tab["layout"] == "yearly":
        return build_yearly_tab(tab)

    kind, label = tab["kind"], tab["label"]
    has_cats = tab["has_categories"]

    if kind == "cashflow":
        kpi_row = html.Div(
            [
                _kpi(
                    f"{kind}-kpi1-label", f"{kind}-kpi1", "Average net / month"
                ),
                _kpi(
                    f"{kind}-kpi2-label", f"{kind}-kpi2", "Total net (period)"
                ),
            ],
            style={"display": "flex", "flexWrap": "wrap"},
        )
    else:
        kpi_row = html.Div(
            [
                _kpi(
                    f"{kind}-kpi1-label",
                    f"{kind}-kpi1",
                    f"Average {label.lower()} / month",
                ),
                _kpi(f"{kind}-kpi2-label", f"{kind}-kpi2", "Total (period)"),
            ],
            style={"display": "flex", "flexWrap": "wrap"},
        )

    controls = _card(
        [
            html.Div(
                [
                    html.Span(
                        "Quick range:",
                        style={
                            "color": C["text_muted"],
                            "marginRight": "10px",
                        },
                    ),
                    _preset_button(kind, "full", "Full"),
                    _preset_button(kind, "year", "This year"),
                    _preset_button(kind, "m12", "Last 12M"),
                    _preset_button(kind, "m6", "Last 6M"),
                    html.Span(
                        id=f"{kind}-range-label",
                        style={
                            "color": C["text"],
                            "float": "right",
                            "fontWeight": "600",
                        },
                    ),
                ],
                style={"marginBottom": "18px"},
            ),
            dcc.RangeSlider(
                id=f"{kind}-range",
                min=0,
                max=N_MONTHS - 1,
                step=1,
                value=[0, N_MONTHS - 1],
                marks=_slider_marks(),
                allowCross=False,
                tooltip={"placement": "bottom", "always_visible": False},
            ),
        ],
    )

    main_chart = _card(dcc.Graph(id=f"{kind}-monthly-graph"))

    body = [kpi_row, controls, main_chart]

    if has_cats:
        detail_row = html.Div(
            [
                html.Div(
                    _card(dcc.Graph(id=f"{kind}-breakdown-graph")),
                    style={"flex": "1", "minWidth": "380px"},
                ),
                html.Div(
                    _card(dcc.Graph(id=f"{kind}-avgcat-graph")),
                    style={"flex": "1", "minWidth": "380px"},
                ),
            ],
            style={"display": "flex", "flexWrap": "wrap"},
        )
        body.append(detail_row)
        body.append(_txn_card(kind))

    return _tab_shell(label, kind, body)


# ---------------------------------------------------------------------------
# Yearly tab (calendar-year totals, yearly category averages, YTD comparison)
# ---------------------------------------------------------------------------
def _section_title(text: str) -> html.Div:
    return html.Div(
        text,
        style={
            "color": C["text"],
            "fontSize": "17px",
            "fontWeight": "600",
            "marginBottom": "12px",
        },
    )


def _control_label(text: str, width: str | None = None) -> html.Span:
    """Muted caption in front of a control; a ``width`` lines up stacked rows."""
    style = {"color": C["text_muted"], "marginRight": "10px"}
    if width:
        style.update(display="inline-block", width=width, marginRight="0")
    return html.Span(text, style=style)


def _radio(component_id: str, options: list[dict], value) -> dcc.RadioItems:
    return dcc.RadioItems(
        id=component_id,
        options=options,
        value=value,
        inline=True,
        style={"display": "inline-block", "color": C["text"]},
        labelStyle={"marginRight": "16px", "cursor": "pointer"},
        inputStyle={"marginRight": "6px"},
    )


def _ytd_kpi(label: str, current: float, previous: float | None) -> html.Div:
    """Year-to-date value with its change against the same period last year."""
    children = [
        html.Div(label, style={"color": C["text_muted"], "fontSize": "15px"}),
        html.Div(
            f"{current:,.0f} €",
            style={
                "color": C["text"],
                "fontSize": "30px",
                "fontWeight": "600",
                "marginTop": "4px",
            },
        ),
    ]
    if previous is not None:
        change = f"{current - previous:+,.0f} €"
        # A percentage of a negative base (cashflow deficit) reads backwards.
        if previous > 0:
            pct = (current - previous) / previous * 100
            change += f" ({pct:+.1f} %)"
        children.append(
            html.Div(
                f"{change} vs. {PAST_YEARS[-1]}, {YTD_SPAN}",
                style={
                    "color": C["text_muted"],
                    "fontSize": "13px",
                    "marginTop": "2px",
                },
            )
        )
    return _card(children, flex="1", minWidth="230px")


def _compare_stat(
    label: str,
    value: str,
    *,
    swatch: str | None = None,
    value_color: str | None = None,
    note: str | None = None,
    first: bool = False,
) -> html.Div:
    """One headline figure of the year comparison: muted label over a large
    value. ``swatch`` repeats the bar color the figure belongs to; ``note``
    trails the value in smaller type."""
    value_children = [value]
    if note:
        value_children.append(
            html.Span(
                note,
                style={
                    "fontSize": "15px",
                    "fontWeight": "400",
                    "marginLeft": "8px",
                },
            )
        )
    label_children = [label]
    if swatch:
        label_children.insert(
            0,
            html.Span(
                style={
                    "display": "inline-block",
                    "width": "10px",
                    "height": "10px",
                    "borderRadius": "2px",
                    "backgroundColor": swatch,
                    "marginRight": "8px",
                }
            ),
        )
    return html.Div(
        [
            html.Div(
                label_children,
                style={"color": C["text_muted"], "fontSize": "13px"},
            ),
            html.Div(
                value_children,
                style={
                    "color": value_color or C["text"],
                    "fontSize": "26px",
                    "fontWeight": "600",
                    "marginTop": "4px",
                    "whiteSpace": "nowrap",
                },
            ),
        ],
        style={
            "padding": "2px 22px",
            "borderLeft": "none" if first else f"1px solid {C['grid']}",
        },
    )


def _graph_pair(left_id: str, right_id: str) -> html.Div:
    return html.Div(
        [
            html.Div(
                dcc.Graph(id=graph_id),
                style={"flex": "1", "minWidth": "380px"},
            )
            for graph_id in (left_id, right_id)
        ],
        style={"display": "flex", "flexWrap": "wrap"},
    )


def build_yearly_tab(tab: dict) -> dcc.Tab:
    ytd = DATA.yearly_totals(ytd=True)
    now = ytd.loc[CURRENT_YEAR]
    prev = ytd.loc[PAST_YEARS[-1]] if PAST_YEARS else None
    kpi_row = html.Div(
        [
            _ytd_kpi(
                f"{label} {CURRENT_YEAR} year to date",
                now[column],
                None if prev is None else prev[column],
            )
            for label, column in (
                ("Income", "total_income"),
                ("Expenses", "total_expense"),
                ("Cashflow", "net"),
            )
        ],
        style={"display": "flex", "flexWrap": "wrap"},
    )

    totals_card = _card(
        [
            _section_title("Income, expenses and cashflow per calendar year"),
            _control_label("Show:"),
            _radio(
                "yearly-totals-mode",
                [
                    {"label": "Full years", "value": "full"},
                    {
                        "label": f"Year to date ({YTD_SPAN} of every year)",
                        "value": "ytd",
                    },
                ],
                "full",
            ),
            dcc.Graph(id="yearly-totals-graph"),
        ]
    )
    body = [kpi_row, totals_card]
    if not PAST_YEARS:
        return _tab_shell(tab["label"], tab["kind"], body)

    year_options = [{"label": str(y), "value": y} for y in DATA.years]
    compare_controls = html.Div(
        [
            _section_title("Expenses by category: compare two years"),
            html.Div(
                [
                    _control_label("Year:", width="110px"),
                    _radio("yearly-compare-year", year_options, CURRENT_YEAR),
                ],
                style={"marginBottom": "8px"},
            ),
            html.Div(
                [
                    _control_label("Compare with:", width="110px"),
                    _radio(
                        "yearly-compare-baseline", year_options, PAST_YEARS[-1]
                    ),
                ],
                style={"marginBottom": "8px"},
            ),
            html.Div(
                [
                    _control_label("Period:", width="110px"),
                    _radio(
                        "yearly-compare-basis",
                        [
                            {
                                "label": f"Year to date ({YTD_SPAN})",
                                "value": "ytd",
                            },
                            {"label": "Full year", "value": "full"},
                        ],
                        "ytd",
                    ),
                ],
            ),
        ]
    )
    compare_card = _card(
        [
            # Controls on the left, the headline totals on the right.
            html.Div(
                [
                    compare_controls,
                    html.Div(
                        id="yearly-compare-summary",
                        style={"display": "flex", "flexWrap": "wrap"},
                    ),
                ],
                style={
                    "display": "flex",
                    "flexWrap": "wrap",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "gap": "16px 24px",
                    "marginBottom": "14px",
                },
            ),
            _graph_pair("yearly-compare-graph", "yearly-delta-graph"),
        ]
    )

    body.append(compare_card)
    return _tab_shell(tab["label"], tab["kind"], body)


# ---------------------------------------------------------------------------
# Portfolio tab (static: positions table + aggregate KPI cards)
# ---------------------------------------------------------------------------
_MONEY = Format(
    group=Group.yes,
    precision=2,
    scheme=Scheme.fixed,
    symbol=Symbol.yes,
    symbol_suffix=" €",
)
_PERCENT = Format(
    precision=1,
    scheme=Scheme.fixed,
    symbol=Symbol.yes,
    symbol_suffix=" %",
)
_SHARES = Format(group=Group.yes, precision=2, scheme=Scheme.fixed)

_PORTFOLIO_TABLE_COLUMNS = [
    {"name": "Group", "id": "group"},
    {"name": "Name", "id": "name"},
    {"name": "Symbol", "id": "symbol"},
    {"name": "ISIN", "id": "isin"},
    {"name": "Ccy", "id": "currency"},
    {"name": "Shares", "id": "shares", "type": "numeric", "format": _SHARES},
    {"name": "Price", "id": "price", "type": "numeric", "format": _MONEY},
    {
        "name": "Investment",
        "id": "investment",
        "type": "numeric",
        "format": _MONEY,
    },
    {"name": "Value", "id": "value", "type": "numeric", "format": _MONEY},
    {"name": "Gain", "id": "gain", "type": "numeric", "format": _MONEY},
    {
        "name": "Gain %",
        "id": "gain_pct",
        "type": "numeric",
        "format": _PERCENT,
    },
    {"name": "As of", "id": "as_of"},
]


def _portfolio_group_card(
    title: str, row: pd.Series, as_of: str | None
) -> html.Div:
    gain = float(row["gain"])
    gain_color = C["positive"] if gain >= 0 else C["negative"]
    subtitle = f"{int(row['n_positions'])} positions"
    if as_of:
        subtitle += f"  ·  as of {as_of}"
    return _card(
        [
            html.Div(
                title, style={"color": C["text_muted"], "fontSize": "15px"}
            ),
            html.Div(
                subtitle, style={"color": C["text_muted"], "fontSize": "12px"}
            ),
            html.Div(
                f"{row['value']:,.0f} €",
                style={
                    "color": C["text"],
                    "fontSize": "30px",
                    "fontWeight": "600",
                    "marginTop": "6px",
                },
            ),
            html.Div(
                [
                    html.Span(
                        "Invested ",
                        style={"color": C["text_muted"], "fontSize": "13px"},
                    ),
                    html.Span(
                        f"{row['investment']:,.0f} €",
                        style={"color": C["text"], "fontSize": "13px"},
                    ),
                ],
                style={"marginTop": "4px"},
            ),
            html.Div(
                f"{gain:+,.0f} €  ({row['gain_pct']:+.1f} %)",
                style={
                    "color": gain_color,
                    "fontSize": "15px",
                    "fontWeight": "600",
                    "marginTop": "2px",
                },
            ),
        ],
        flex="1",
        minWidth="230px",
    )


def build_portfolio_tab(tab: dict) -> dcc.Tab:
    agg = PORTFOLIO.group_aggregates()
    as_of = PORTFOLIO.as_of_by_group()

    cards = [_portfolio_group_card("Total Portfolio", agg.loc["All"], None)]
    for grp in ("ETFs", "Stocks"):
        if grp in agg.index:
            cards.append(
                _portfolio_group_card(grp, agg.loc[grp], as_of.get(grp))
            )
    kpi_row = html.Div(cards, style={"display": "flex", "flexWrap": "wrap"})

    records = PORTFOLIO.positions.copy()
    records["as_of"] = pd.to_datetime(records["as_of"]).dt.strftime("%Y-%m-%d")

    table = _card(
        dash_table.DataTable(
            id="portfolio-table",
            columns=_PORTFOLIO_TABLE_COLUMNS,
            data=records.to_dict("records"),
            sort_action="native",
            filter_action="native",
            page_size=40,
            style_as_list_view=True,
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": C["background"],
                "color": C["text"],
                "fontWeight": "600",
                "border": "none",
                "borderBottom": f"2px solid {C['grid']}",
            },
            style_cell={
                "backgroundColor": C["panel"],
                "color": C["text"],
                "border": "none",
                "borderBottom": f"1px solid {C['grid']}",
                "padding": "8px 10px",
                "fontFamily": "Segoe UI, Arial, sans-serif",
                "fontSize": "13px",
                "textAlign": "right",
                "maxWidth": "320px",
                "overflow": "hidden",
                "textOverflow": "ellipsis",
            },
            style_cell_conditional=[
                {"if": {"column_id": c}, "textAlign": "left"}
                for c in (
                    "group",
                    "name",
                    "symbol",
                    "isin",
                    "currency",
                    "as_of",
                )
            ],
            style_data_conditional=[
                {
                    "if": {"filter_query": "{gain} < 0", "column_id": "gain"},
                    "color": C["negative"],
                },
                {
                    "if": {"filter_query": "{gain} >= 0", "column_id": "gain"},
                    "color": C["positive"],
                },
                {
                    "if": {
                        "filter_query": "{gain_pct} < 0",
                        "column_id": "gain_pct",
                    },
                    "color": C["negative"],
                },
                {
                    "if": {
                        "filter_query": "{gain_pct} >= 0",
                        "column_id": "gain_pct",
                    },
                    "color": C["positive"],
                },
            ],
        ),
    )

    return _tab_shell(tab["label"], tab["kind"], [kpi_row, table])


def build_layout() -> html.Div:
    return html.Div(
        [
            html.H1(
                "Personal Finance Dashboard",
                style={"color": C["text"], "padding": "14px 22px 0"},
            ),
            dcc.Tabs(
                id="main-tabs",
                value=KINDS[0],
                children=[build_tab(t) for t in TABS],
                style={"marginTop": "8px"},
            ),
        ],
        style={
            "backgroundColor": C["background"],
            "minHeight": "100vh",
            "fontFamily": "Segoe UI, Arial, sans-serif",
        },
    )


# ---------------------------------------------------------------------------
# App + callbacks
# ---------------------------------------------------------------------------
app = Dash(
    __name__,
    title="Personal Finance Dashboard",
    suppress_callback_exceptions=True,
)
app.layout = build_layout()


def _register_callbacks() -> None:
    for tab in TABS:
        if tab["layout"] != "series":
            # portfolio tab is static; the yearly tab registers its own
            continue
        kind = tab["kind"]
        has_cats = tab["has_categories"]

        # Preset buttons -> write the slider value (single source of truth).
        @app.callback(
            Output(f"{kind}-range", "value"),
            Input(f"{kind}-preset-full", "n_clicks"),
            Input(f"{kind}-preset-year", "n_clicks"),
            Input(f"{kind}-preset-m12", "n_clicks"),
            Input(f"{kind}-preset-m6", "n_clicks"),
            prevent_initial_call=True,
        )
        def _apply_preset(*_clicks, kind=kind):
            trigger = callback_context.triggered_id or ""
            preset = trigger.rsplit("-", 1)[-1]
            return _preset_range(preset)

        # Slider (+ bar click for category tabs) -> figures & KPIs.
        if has_cats:

            @app.callback(
                Output(f"{kind}-monthly-graph", "figure"),
                Output(f"{kind}-breakdown-graph", "figure"),
                Output(f"{kind}-avgcat-graph", "figure"),
                Output(f"{kind}-kpi1", "children"),
                Output(f"{kind}-kpi2", "children"),
                Output(f"{kind}-range-label", "children"),
                Input(f"{kind}-range", "value"),
                Input(f"{kind}-monthly-graph", "clickData"),
                prevent_initial_call=False,
            )
            def _update_cat(rng, click_data, kind=kind):
                sub, sel = _sub_and_selected(
                    rng, click_data, f"{kind}-monthly-graph"
                )
                monthly_fig = figures.monthly_bar_figure(sub, kind, sel)
                breakdown_fig = figures.category_breakdown_figure(
                    sub, kind, sel
                )
                avgcat_fig = figures.category_average_figure(sub, kind)
                total = sub.totals(kind).sum()
                avg = sub.totals(kind).mean() if len(sub.months) else 0.0
                return (
                    monthly_fig,
                    breakdown_fig,
                    avgcat_fig,
                    f"{avg:,.0f} €",
                    f"{total:,.0f} €",
                    _range_label(rng),
                )

            # Category bar click (monthly breakdown or period average) -> the
            # list of transactions behind that category, scoped accordingly.
            @app.callback(
                Output(f"{kind}-txn-title", "children"),
                Output(f"{kind}-txn-table", "data"),
                Input(f"{kind}-range", "value"),
                Input(f"{kind}-monthly-graph", "clickData"),
                Input(f"{kind}-breakdown-graph", "clickData"),
                Input(f"{kind}-avgcat-graph", "clickData"),
                prevent_initial_call=False,
            )
            def _update_txns(rng, month_click, bd_click, avg_click, kind=kind):
                placeholder = (
                    "Click a category bar above to list its transactions"
                )
                start, end = _clamp_range(rng)
                sub = DATA.slice_months(MONTHS[start], MONTHS[end])
                sub_months = sub.months
                if not sub_months:
                    return placeholder, []

                trigger = callback_context.triggered_id
                bd_id = f"{kind}-breakdown-graph"
                avg_id = f"{kind}-avgcat-graph"

                if trigger == avg_id and avg_click:
                    category = avg_click["points"][0]["y"]
                    txns = sub.transactions(kind, category)
                    scope = _range_label(rng)
                elif trigger == bd_id and bd_click:
                    category = bd_click["points"][0]["y"]
                    month = _selected_month(sub_months, month_click)
                    txns = sub.transactions(kind, category, month=month)
                    scope = _month_label(month)
                else:
                    # Range/month change (or startup): clear stale selection.
                    return placeholder, []

                title = f"{category} — {scope}  ·  {len(txns)} transactions"
                data = [
                    {
                        "date": d.strftime("%Y-%m-%d"),
                        "tag": t,
                        "amount": a,
                    }
                    for d, t, a in zip(
                        txns["date"], txns["tag"], txns["amount"]
                    )
                ]
                return title, data

        else:

            @app.callback(
                Output(f"{kind}-monthly-graph", "figure"),
                Output(f"{kind}-kpi1", "children"),
                Output(f"{kind}-kpi2", "children"),
                Output(f"{kind}-range-label", "children"),
                Input(f"{kind}-range", "value"),
                prevent_initial_call=False,
            )
            def _update_plain(rng, kind=kind):
                sub, _ = _sub_and_selected(rng, None, None)
                monthly_fig = figures.monthly_bar_figure(sub, kind, None)
                total = sub.totals(kind).sum()
                avg = sub.totals(kind).mean() if len(sub.months) else 0.0
                return (
                    monthly_fig,
                    f"{avg:,.0f} €",
                    f"{total:,.0f} €",
                    _range_label(rng),
                )


def _register_yearly_callbacks() -> None:
    @app.callback(
        Output("yearly-totals-graph", "figure"),
        Input("yearly-totals-mode", "value"),
    )
    def _update_totals(mode):
        if mode == "ytd":
            return figures.yearly_totals_figure(DATA.yearly_totals(ytd=True))
        return figures.yearly_totals_figure(
            DATA.yearly_totals(),
            partial_year=None if YEAR_COMPLETE else CURRENT_YEAR,
        )

    if not PAST_YEARS:
        return  # nothing to compare against yet

    @app.callback(
        Output("yearly-compare-graph", "figure"),
        Output("yearly-delta-graph", "figure"),
        Output("yearly-compare-summary", "children"),
        Input("yearly-compare-year", "value"),
        Input("yearly-compare-baseline", "value"),
        Input("yearly-compare-basis", "value"),
    )
    def _update_comparison(year, baseline, basis):
        same_period = basis != "full"

        def _label(y: int) -> str:
            if same_period:
                return f"{y} ({YTD_SPAN})"
            # The running year has no full year yet: it stops at the cutoff.
            if y == CURRENT_YEAR and not YEAR_COMPLETE:
                return f"{y} YTD"
            return f"{y} full year"

        current = DATA.category_year_totals("expenses", year, ytd=same_period)
        past = DATA.category_year_totals("expenses", baseline, ytd=same_period)
        current_label, past_label = _label(year), _label(baseline)

        change = current.sum() - past.sum()
        change_pct = (
            f"{change / past.sum() * 100:+.1f} %" if past.sum() else None
        )
        summary = [
            _compare_stat(
                current_label,
                f"{current.sum():,.0f} €",
                swatch=C["expense"],
                first=True,
            ),
            _compare_stat(
                past_label, f"{past.sum():,.0f} €", swatch=C["reference"]
            ),
            # Spending less than in the baseline year is the good direction.
            _compare_stat(
                "Change",
                f"{change:+,.0f} €",
                value_color=C["positive"] if change <= 0 else C["negative"],
                note=change_pct,
            ),
        ]
        return (
            figures.category_comparison_figure(
                current, past, current_label, past_label, "expenses"
            ),
            figures.category_delta_figure(
                current, past, past_label, "expenses"
            ),
            summary,
        )


def _range_label(rng) -> str:
    start, end = _clamp_range(rng)
    return f"{_month_label(MONTHS[start])} – {_month_label(MONTHS[end])}"


def _clamp_range(rng) -> tuple[int, int]:
    if not rng:
        return 0, N_MONTHS - 1
    start, end = int(rng[0]), int(rng[1])
    start = max(0, min(start, N_MONTHS - 1))
    end = max(0, min(end, N_MONTHS - 1))
    if start > end:
        start, end = end, start
    return start, end


def _selected_month(sub_months, click_data):
    """Resolve the highlighted month from a monthly-bar click, regardless of
    which component triggered the current callback (defaults to last month)."""
    if not sub_months:
        return None
    selected = sub_months[-1]
    if click_data:
        try:
            clicked = (
                pd.Timestamp(click_data["points"][0]["x"])
                .to_period("M")
                .to_timestamp()
            )
            if clicked in sub_months:
                selected = clicked
        except (KeyError, IndexError, ValueError):
            pass
    return selected


def _sub_and_selected(rng, click_data, graph_id):
    """Slice DATA to the selected range and resolve the highlighted month."""
    start, end = _clamp_range(rng)
    sub = DATA.slice_months(MONTHS[start], MONTHS[end])
    sub_months = sub.months
    if not sub_months:
        return sub, None

    selected = sub_months[-1]
    trigger = callback_context.triggered_id
    if graph_id is not None and trigger == graph_id and click_data:
        try:
            clicked = (
                pd.Timestamp(click_data["points"][0]["x"])
                .to_period("M")
                .to_timestamp()
            )
            if clicked in sub_months:
                selected = clicked
        except (KeyError, IndexError, ValueError):
            pass
    return sub, selected


_register_callbacks()
_register_yearly_callbacks()


def main() -> None:
    import os

    debug = os.environ.get("DASH_DEBUG", "1") not in ("0", "false", "False")
    reload = os.environ.get("DASH_RELOAD", "0") not in ("0", "false", "False")
    port = int(os.environ.get("DASH_PORT", "8050"))
    app.run(debug=debug, use_reloader=reload, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()

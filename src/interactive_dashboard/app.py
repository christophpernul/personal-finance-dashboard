"""Interactive personal-finance dashboard (Plotly Dash).

Tabs: Expenses, Income, Cashflow. Each tab lets you freely pick a month range
(slider + presets), shows monthly bars with the period average, and — for
Expenses/Income — drills into per-category spend when you click a month, plus the
average spend per category over the selected period.

Run with::

    python -m src.dashboard.interactive_dashboard.app
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

PORTFOLIO: PortfolioData = load_portfolio_data()

# Tab registry — add a dict here to introduce a new tab later.
# ``layout`` selects how the tab is rendered: "series" = monthly bars + range
# slider; "portfolio" = positions table + aggregate KPI cards.
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
            continue  # portfolio tab is static — no callbacks
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


def main() -> None:
    import os

    debug = os.environ.get("DASH_DEBUG", "1") not in ("0", "false", "False")
    reload = os.environ.get("DASH_RELOAD", "0") not in ("0", "false", "False")
    port = int(os.environ.get("DASH_PORT", "8050"))
    app.run(debug=debug, use_reloader=reload, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()

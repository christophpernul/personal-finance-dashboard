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
from dash import Dash, Input, Output, State, callback_context, dcc, html

from . import config, figures
from .data import FinanceData, load_finance_data

C = config.COLORS

# --- Load data once at startup ----------------------------------------------
DATA: FinanceData = load_finance_data()
MONTHS: list[pd.Timestamp] = DATA.months
N_MONTHS = len(MONTHS)

# Tab registry — add a dict here to introduce a new tab later.
TABS = [
    {"kind": "expenses", "label": "Expenses", "has_categories": True},
    {"kind": "income", "label": "Income", "has_categories": True},
    {"kind": "cashflow", "label": "Cashflow", "has_categories": False},
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


def build_tab(tab: dict) -> dcc.Tab:
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

    return dcc.Tab(
        label=label,
        value=kind,
        children=html.Div(body, style={"padding": "6px"}),
        style={
            "backgroundColor": C["background"],
            "color": C["text_muted"],
            "border": f"1px solid {C['grid']}",
        },
        selected_style={
            "backgroundColor": C["panel"],
            "color": C["text"],
            "border": f"1px solid {C['grid']}",
            "borderTop": f"3px solid {C['average']}",
        },
    )


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

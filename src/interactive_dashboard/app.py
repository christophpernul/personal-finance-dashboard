"""Interactive personal-finance dashboard (Plotly Dash).

The top-level navigation has two sections: Cashflow (Expenses, Income,
Cashflow, Yearly and Transactions tabs) and Investment (Portfolio tab).

Expenses, Income, Cashflow: each tab lets you freely pick a month range
(slider + presets), shows monthly bars with the period average, and — for
Expenses/Income — drills into per-category spend when you click a month, plus the
average spend per category over the selected period.

The Yearly tab aggregates per calendar year: income/expenses/cashflow totals
(full year or year-to-date) and a per-category comparison of the expenses of
any two years.

The Transactions tab lists every expense and income transaction in one
sortable, filterable table, with totals of whatever the filters leave over.

Run with::

    python -m src.interactive_dashboard.app
"""
from __future__ import annotations

import calendar
from typing import Callable, NamedTuple

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
    no_update,
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

# Tab registry — add a dict to a section's ``tabs`` to introduce a new tab
# later. Each section is a top-level navigation item holding its own row of
# tabs. ``layout`` selects how a tab is rendered: "series" = monthly bars +
# range slider; "yearly" = calendar-year totals + category comparisons;
# "portfolio" = positions table + aggregate KPI cards; "transactions" = table
# of all transactions.
SECTIONS = [
    {
        "key": "cashflow-section",
        "label": "Cashflow",
        "tabs": [
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
            {
                "kind": "transactions",
                "label": "Transactions",
                "layout": "transactions",
            },
        ],
    },
    {
        "key": "investment-section",
        "label": "Investment",
        "tabs": [
            {"kind": "portfolio", "label": "Portfolio", "layout": "portfolio"},
        ],
    },
]
TABS = [tab for section in SECTIONS for tab in section["tabs"]]


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
                    {"name": "Comment", "id": "description"},
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
                    for c in ("date", "tag", "description")
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
    if tab["layout"] == "transactions":
        return build_transactions_tab(tab)

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
# Dropdown filters (shared by the Portfolio and Transactions tables)
# ---------------------------------------------------------------------------
class _DropdownSpec(NamedTuple):
    """A checkbox dropdown listing the distinct values of one column."""

    col: str
    label: str
    width: str
    fmt: Callable = str  # value -> option label
    searchable: bool = False  # search box above the options (long lists)


def _dropdown_options(
    rows: pd.DataFrame, spec: _DropdownSpec, selected: list | None
) -> list[dict]:
    """Distinct values of ``spec.col`` in ``rows`` with their row counts.

    Selected values stay listed (with count 0) even if the other filters no
    longer leave a row for them, so they can still be deselected.
    """
    # Blank values (e.g. transactions without a comment) are not offered.
    counts = rows[spec.col].replace("", pd.NA).dropna().value_counts()
    values = sorted(set(counts.index) | set(selected or []))
    return [
        {
            "label": f"{spec.fmt(v)}  ({counts.get(v, 0)})",
            # numpy scalars -> plain Python for the JSON round trip
            "value": v.item() if hasattr(v, "item") else v,
        }
        for v in values
    ]


def _search_options(
    options: list[dict], search: str | None, selected: list | None
) -> list[dict]:
    """Options whose label contains ``search``; ticked ones always stay."""
    needle = (search or "").strip().lower()
    if not needle:
        return options
    return [
        o
        for o in options
        if needle in o["label"].lower() or o["value"] in (selected or [])
    ]


def _dropdown_label(spec: _DropdownSpec, selected: list | None) -> str:
    """Closed-dropdown text: "All" or the ticked values."""
    if not selected:
        return "All"
    return ", ".join(spec.fmt(v) for v in sorted(selected))


def _check_dropdown(
    component_id: str, spec: _DropdownSpec, options: list[dict]
) -> html.Details:
    """A dropdown that stays open while ticking several values.

    The checklist itself carries ``component_id`` (``value`` = ticked values,
    ``options`` = choices); ``{component_id}-label`` shows the selection while
    closed and ``{component_id}-search`` narrows long option lists.
    assets/check_dropdown.js closes it on a click outside or on Escape.
    """
    menu = [
        dcc.Checklist(
            id=component_id,
            options=options,
            value=[],
            className="check-dropdown-list",
            labelClassName="check-dropdown-option",
        )
    ]
    if spec.searchable:
        menu.insert(
            0,
            dcc.Input(
                id=f"{component_id}-search",
                type="text",
                placeholder="Search…",
                value="",
                className="check-dropdown-search",
            ),
        )
    return html.Details(
        [
            html.Summary(
                [
                    html.Span(
                        "All",
                        id=f"{component_id}-label",
                        className="check-dropdown-label",
                    ),
                    html.Span("▾", className="check-dropdown-arrow"),
                ]
            ),
            html.Div(menu, className="check-dropdown-menu"),
        ],
        className="check-dropdown",
    )


def _filter_by_dropdowns(
    df: pd.DataFrame, selections: dict[str, list], skip: str | None = None
) -> pd.DataFrame:
    """Rows matching every dropdown selection; ``skip`` ignores that column."""
    for col, selected in selections.items():
        if col != skip and selected:
            df = df[df[col].isin(selected)]
    return df


def _labelled_control(text: str, control, width: str) -> html.Div:
    return html.Div(
        [
            html.Div(
                text,
                style={
                    "color": C["text_muted"],
                    "fontSize": "12px",
                    "marginBottom": "4px",
                },
            ),
            control,
        ],
        style={"width": width, "margin": "0 12px 10px 0"},
    )


def _filter_controls(
    prefix: str,
    rows: pd.DataFrame,
    specs: list[_DropdownSpec],
    extra: list | None = None,
    hint: str = "",
) -> html.Div:
    """Dropdowns ``{prefix}-dd-<col>``, extra controls and a reset button."""
    dropdowns = [
        _labelled_control(
            spec.label,
            _check_dropdown(
                f"{prefix}-dd-{spec.col}",
                spec,
                _dropdown_options(rows, spec, []),
            ),
            spec.width,
        )
        for spec in specs
    ]
    reset = html.Button(
        "Reset filters & sort",
        id=f"{prefix}-reset",
        n_clicks=0,
        style={
            "backgroundColor": C["background"],
            "color": C["text"],
            "border": f"1px solid {C['grid']}",
            "borderRadius": "6px",
            "padding": "6px 14px",
            "marginBottom": "10px",
            "cursor": "pointer",
        },
    )
    return html.Div(
        [
            html.Div(
                [*dropdowns, *(extra or []), reset],
                style={
                    "display": "flex",
                    "flexWrap": "wrap",
                    "alignItems": "flex-end",
                },
            ),
            html.Div(
                "Tick one or more values per filter; each lists the distinct "
                "values (with row counts) left by the other filters. Click a "
                f"column header to sort (asc → desc → off{hint}).",
                style={"color": C["text_muted"], "fontSize": "12px"},
            ),
        ],
    )


def _register_filter_callbacks(
    prefix: str,
    specs: list[_DropdownSpec],
    filter_rows: Callable[..., pd.DataFrame],
    extra_inputs: dict[str, object] | None = None,
) -> None:
    """Wire the dropdowns (+ extra inputs) of ``_filter_controls`` to
    ``{prefix}-table``.

    ``filter_rows(selections, *extra_values, skip=None)`` returns the matching
    rows; ``extra_inputs`` maps further control ids to their reset value.
    """
    extra_inputs = extra_inputs or {}
    dd_ids = [f"{prefix}-dd-{spec.col}" for spec in specs]
    search_specs = [spec for spec in specs if spec.searchable]
    search_ids = [f"{prefix}-dd-{spec.col}-search" for spec in search_specs]

    # Filters -> rows fed into the table (its native sort applies on top),
    # plus each dropdown's options (the distinct values left by all *other*
    # filters, narrowed by its search box) and its closed-state label.
    @app.callback(
        Output(f"{prefix}-table", "data"),
        *[Output(i, "options") for i in dd_ids],
        *[Output(f"{i}-label", "children") for i in dd_ids],
        *[Input(i, "value") for i in extra_inputs],
        *[Input(i, "value") for i in dd_ids],
        *[Input(i, "value") for i in search_ids],
    )
    def _filter(*values):
        n_extra, n_dd = len(extra_inputs), len(dd_ids)
        extra = values[:n_extra]
        selected = values[n_extra : n_extra + n_dd]
        searches = dict(
            zip((s.col for s in search_specs), values[n_extra + n_dd :])
        )
        selections = {spec.col: sel for spec, sel in zip(specs, selected)}
        rows = filter_rows(selections, *extra)
        options = [
            _search_options(
                _dropdown_options(
                    filter_rows(selections, *extra, skip=spec.col),
                    spec,
                    selections[spec.col],
                ),
                searches.get(spec.col),
                selections[spec.col],
            )
            for spec in specs
        ]
        labels = [
            _dropdown_label(spec, selections[spec.col]) for spec in specs
        ]
        # Typing in a search box only narrows that dropdown's options; the
        # table rows are unchanged, so don't resend them on every keystroke.
        if callback_context.triggered_id in search_ids:
            return [no_update, *options, *labels]
        return [rows.to_dict("records"), *options, *labels]

    @app.callback(
        *[Output(i, "value") for i in extra_inputs],
        *[Output(i, "value") for i in dd_ids],
        *[Output(i, "value") for i in search_ids],
        Output(f"{prefix}-table", "sort_by"),
        Input(f"{prefix}-reset", "n_clicks"),
        prevent_initial_call=True,
    )
    def _reset(_n):
        return [
            *extra_inputs.values(),
            *[[] for _ in dd_ids],
            *["" for _ in search_ids],
            [],
        ]


# ---------------------------------------------------------------------------
# Portfolio tab (filterable positions table + aggregate KPI cards)
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

    table = _card(
        [
            _portfolio_controls(),
            html.Div(
                id="portfolio-summary",
                style={
                    "color": C["text_muted"],
                    "fontSize": "13px",
                    "margin": "12px 0 8px",
                },
            ),
            _portfolio_table(),
        ]
    )

    return _tab_shell(tab["label"], tab["kind"], [kpi_row, table])


def _portfolio_records() -> pd.DataFrame:
    records = PORTFOLIO.positions.copy()
    records["as_of"] = pd.to_datetime(records["as_of"]).dt.strftime("%Y-%m-%d")
    return records


_PORTFOLIO_RECORDS = _portfolio_records()


_PORTFOLIO_DROPDOWNS = [
    _DropdownSpec("group", "Group", "190px"),
    _DropdownSpec("name", "Name", "380px", searchable=True),
]


def _portfolio_controls() -> html.Div:
    """Group/name dropdowns, gainers/losers filter and reset button."""
    performance = _labelled_control(
        "Show",
        _radio(
            "portfolio-performance",
            [
                {"label": "All", "value": "all"},
                {"label": "Gainers", "value": "gain"},
                {"label": "Losers", "value": "loss"},
            ],
            "all",
        ),
        "auto",
    )
    return _filter_controls(
        "portfolio",
        _PORTFOLIO_RECORDS,
        _PORTFOLIO_DROPDOWNS,
        extra=[performance],
    )


def _filter_portfolio(
    selections: dict[str, list], performance: str, skip: str | None = None
) -> pd.DataFrame:
    df = _filter_by_dropdowns(_PORTFOLIO_RECORDS, selections, skip)
    if performance == "gain":
        df = df[df["gain"] > 0]
    elif performance == "loss":
        df = df[df["gain"] < 0]
    return df


def _portfolio_summary(rows: list[dict] | None) -> list:
    rows = rows or []
    df = pd.DataFrame(rows, columns=["value", "investment", "gain"])
    value, invested, gain = (
        pd.to_numeric(df[c], errors="coerce").sum()
        for c in ("value", "investment", "gain")
    )
    pct = gain / invested * 100 if invested else 0.0
    gain_color = C["positive"] if gain >= 0 else C["negative"]
    strong = {"color": C["text"], "fontWeight": "600"}
    return [
        html.Span(
            f"{len(rows)} of {len(_PORTFOLIO_RECORDS)} positions",
            style=strong,
        ),
        "  ·  Value ",
        html.Span(f"{value:,.0f} €", style=strong),
        "  ·  Invested ",
        html.Span(f"{invested:,.0f} €", style=strong),
        "  ·  Gain ",
        html.Span(
            f"{gain:+,.0f} € ({pct:+.1f} %)",
            style={**strong, "color": gain_color},
        ),
    ]


def _portfolio_table() -> dash_table.DataTable:
    return dash_table.DataTable(
        id="portfolio-table",
        columns=_PORTFOLIO_TABLE_COLUMNS,
        data=_PORTFOLIO_RECORDS.to_dict("records"),
        sort_action="native",
        sort_by=[],
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
    )


# ---------------------------------------------------------------------------
# Transactions tab (every expense and income transaction, sort + filter)
# ---------------------------------------------------------------------------
_TXN_TABLE_COLUMNS = [
    {"name": "Date", "id": "date", "type": "datetime"},
    {"name": "Category", "id": "category"},
    {"name": "Tag", "id": "tag"},
    {"name": "Comment", "id": "description"},
    {"name": "Type", "id": "type"},
    {"name": "Amount", "id": "amount", "type": "numeric", "format": _MONEY},
    {"name": "Year", "id": "year", "type": "numeric"},
    {"name": "Month", "id": "month", "type": "numeric"},
]
_TXN_DROPDOWNS = [
    _DropdownSpec("type", "Type", "210px"),
    _DropdownSpec("year", "Year", "190px"),
    _DropdownSpec("month", "Month", "190px", lambda m: calendar.month_abbr[m]),
    _DropdownSpec("category", "Category", "260px", searchable=True),
    _DropdownSpec("tag", "Tag", "260px", searchable=True),
    _DropdownSpec("description", "Comment", "340px", searchable=True),
]


def _transaction_records() -> pd.DataFrame:
    txns = DATA.all_transactions()
    return pd.DataFrame(
        {
            "date": txns["date"].dt.strftime("%Y-%m-%d"),
            "category": txns["category"],
            "tag": txns["tag"],
            "description": txns["description"],
            "type": txns["type"],
            "amount": txns["amount"],
            "year": txns["date"].dt.year,
            "month": txns["date"].dt.month,
        }
    ).reset_index(drop=True)


_TXN_RECORDS = _transaction_records()


def _filter_transactions(
    selections: dict[str, list], skip: str | None = None
) -> pd.DataFrame:
    return _filter_by_dropdowns(_TXN_RECORDS, selections, skip)


def _transactions_summary(rows: list[dict] | None) -> list:
    rows = rows or []
    expense = sum(r["amount"] for r in rows if r["type"] == "Expense")
    income = sum(r["amount"] for r in rows if r["type"] == "Income")
    net = income - expense
    strong = {"color": C["text"], "fontWeight": "600"}
    return [
        html.Span(
            f"{len(rows):,} of {len(_TXN_RECORDS):,} transactions",
            style=strong,
        ),
        "  ·  Income ",
        html.Span(f"{income:,.2f} €", style={**strong, "color": C["income"]}),
        "  ·  Expenses ",
        html.Span(
            f"{expense:,.2f} €", style={**strong, "color": C["expense"]}
        ),
        "  ·  Net ",
        html.Span(
            f"{net:+,.2f} €",
            style={
                **strong,
                "color": C["positive"] if net >= 0 else C["negative"],
            },
        ),
    ]


def _transactions_table() -> dash_table.DataTable:
    return dash_table.DataTable(
        id="transactions-table",
        columns=_TXN_TABLE_COLUMNS,
        data=_TXN_RECORDS.to_dict("records"),
        sort_action="native",
        sort_mode="multi",
        sort_by=[],
        page_size=50,
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
            for c in ("date", "category", "tag", "description", "type")
        ],
        style_data_conditional=[
            {
                "if": {
                    "filter_query": f'{{type}} = "{kind}"',
                    "column_id": col,
                },
                "color": color,
            }
            for kind, color in (
                ("Expense", C["expense"]),
                ("Income", C["income"]),
            )
            for col in ("type", "amount")
        ],
    )


def build_transactions_tab(tab: dict) -> dcc.Tab:
    controls = _filter_controls(
        "transactions",
        _TXN_RECORDS,
        _TXN_DROPDOWNS,
        hint="; shift-click to add a column",
    )
    table = _card(
        [
            controls,
            html.Div(
                id="transactions-summary",
                style={
                    "color": C["text_muted"],
                    "fontSize": "13px",
                    "margin": "12px 0 8px",
                },
            ),
            _transactions_table(),
        ]
    )
    return _tab_shell(tab["label"], tab["kind"], [table])


def build_section(section: dict) -> dcc.Tab:
    """Top-level navigation item holding the row of tabs of one section."""
    tabs = section["tabs"]
    return dcc.Tab(
        label=section["label"],
        value=section["key"],
        children=dcc.Tabs(
            id=f"{section['key']}-tabs",
            value=tabs[0]["kind"],
            children=[build_tab(t) for t in tabs],
            style={"marginTop": "10px"},
        ),
        style={
            "backgroundColor": C["background"],
            "color": C["text_muted"],
            "border": "none",
            "borderBottom": f"2px solid {C['grid']}",
            "fontSize": "17px",
            "fontWeight": "600",
            "padding": "10px 20px",
        },
        selected_style={
            "backgroundColor": C["background"],
            "color": C["text"],
            "border": "none",
            "borderBottom": f"3px solid {C['average']}",
            "fontSize": "17px",
            "fontWeight": "600",
            "padding": "10px 20px",
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
                value=SECTIONS[0]["key"],
                children=[build_section(s) for s in SECTIONS],
                style={"marginTop": "8px", "maxWidth": "480px"},
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
            # the yearly and portfolio tabs register their own
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
                        "description": c,
                        "amount": a,
                    }
                    for d, t, c, a in zip(
                        txns["date"],
                        txns["tag"],
                        txns["description"],
                        txns["amount"],
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


def _register_transactions_callbacks() -> None:
    _register_filter_callbacks(
        "transactions", _TXN_DROPDOWNS, _filter_transactions
    )

    # Totals of exactly what is left after the filters (all pages).
    @app.callback(
        Output("transactions-summary", "children"),
        Input("transactions-table", "derived_virtual_data"),
    )
    def _update_summary(rows):
        return _transactions_summary(rows)


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


def _register_portfolio_callbacks() -> None:
    _register_filter_callbacks(
        "portfolio",
        _PORTFOLIO_DROPDOWNS,
        _filter_portfolio,
        extra_inputs={"portfolio-performance": "all"},
    )

    # Totals of exactly what is visible after all filters (all pages).
    @app.callback(
        Output("portfolio-summary", "children"),
        Input("portfolio-table", "derived_virtual_data"),
    )
    def _update_summary(rows):
        return _portfolio_summary(rows)


_register_callbacks()
_register_yearly_callbacks()
_register_transactions_callbacks()
_register_portfolio_callbacks()


def main() -> None:
    import os

    debug = os.environ.get("DASH_DEBUG", "1") not in ("0", "false", "False")
    reload = os.environ.get("DASH_RELOAD", "0") not in ("0", "false", "False")
    port = int(os.environ.get("DASH_PORT", "8050"))
    app.run(debug=debug, use_reloader=reload, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()

"""Interactive personal-finance dashboard (Plotly Dash).

The top-level navigation has two sections: Cashflow (Expenses, Income,
Cashflow, Yearly and Transactions tabs) and Investment (Portfolio and Sold
Positions tabs).

Expenses, Income, Cashflow: each tab lets you freely pick a month range
(slider + presets), shows monthly bars with the period average, and — for
Expenses/Income — drills into per-category spend when you click a month, plus the
average spend per category over the selected period.

The Yearly tab aggregates per calendar year: income/expenses/cashflow totals
(full year or year-to-date) and a per-category comparison of the expenses of
any two years.

The Transactions tab lists every expense and income transaction in one
sortable, filterable table, with totals of whatever the filters leave over.

The Allocation tab splits the holdings (all asset classes, or any combination
of ETFs, stocks, Riester, crypto and cash) by region, accumulating vs.
distributing, physical vs. synthetic and ETF type (count, value and share)
and shows their average TER, ongoing costs per year and costs so far.

The Monthly Savings plan tab shows the latest execution of the ETF savings
plan: which ETFs it buys for how much, split by region and accumulating vs.
distributing.

The Earnings tab shows the dividends and interest (Tagesgeld, Festgeld)
received per year as stacked bars, by type or by holding, over any range of
years; clicking a year breaks it down by holding. It also ranks the dividends of
the current year per holding and lists the dividends of every holding per year.

The Sold Positions tab lists every sold ETF/stock position with what it was
bought and sold for, its dividends and costs, net profit and return; clicking a
position lists its single cashflows.

The Balancesheet tab (Balance Sheet section) shows the balance and interest
rate of every account, the running fixed-term deposits and how long they keep
money bound, the liabilities (credit cards, loans), and all cash split into
available and bound per month.

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
from dash.dash_table.Format import Format, Group, Scheme, Symbol, Trim

from . import config, figures
from .allocation import (
    ASSET_CLASSES,
    DIMENSION_BY_COL,
    DIMENSIONS,
    UNKNOWN,
    Dimension,
    breakdown,
    build_holdings,
    cost_summary,
    select,
)
from .cash import STATUS_LABELS, STATUS_MATURED, CashData, load_cash_data
from .data import FinanceData, load_finance_data
from .portfolio import (
    GROUP_ORDER,
    PortfolioData,
    load_portfolio_data,
    weighted_ter,
)
from .earnings import (
    KIND_DIVIDEND,
    KIND_INTEREST,
    EarningsData,
    load_earnings_data,
)
from .savings_plan import SavingsPlan, load_savings_plan
from .sold_positions import (
    SOLD_GROUP_ORDER,
    SoldPositionsData,
    load_sold_positions_data,
)

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
SOLD: SoldPositionsData = load_sold_positions_data()
CASH: CashData | None = load_cash_data()
SAVINGS_PLAN: SavingsPlan | None = load_savings_plan()
EARNINGS: EarningsData | None = load_earnings_data()
HOLDINGS: pd.DataFrame = build_holdings(PORTFOLIO, CASH)

# Tab registry — add a dict to a section's ``tabs`` to introduce a new tab
# later. Each section is a top-level navigation item holding its own row of
# tabs. ``layout`` selects how a tab is rendered: "series" = monthly bars +
# range slider; "yearly" = calendar-year totals + category comparisons;
# "portfolio" = positions table + aggregate KPI cards; "transactions" = table
# of all transactions; "sold" = sold positions table + KPI cards + drill-down;
# "cash" = account balances, fixed-term deposits and available vs. bound cash;
# "allocation" = holdings split by region / distribution / replication / type
# plus TER and costs, for any combination of asset classes; "earnings" =
# dividends and interest per year and holding.
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
            {
                "kind": "allocation",
                "label": "Allocation",
                "layout": "allocation",
            },
            {
                "kind": "savings-plan",
                "label": "Monthly Savings plan",
                "layout": "savings_plan",
            },
            {"kind": "earnings", "label": "Earnings", "layout": "earnings"},
            {"kind": "sold", "label": "Sold Positions", "layout": "sold"},
        ],
    },
    {
        "key": "balance-section",
        "label": "Balance Sheet",
        "tabs": [{"kind": "cash", "label": "Balancesheet", "layout": "cash"}],
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
    if tab["layout"] == "sold":
        return build_sold_tab(tab)
    if tab["layout"] == "cash":
        return build_cash_tab(tab)
    if tab["layout"] == "allocation":
        return build_allocation_tab(tab)
    if tab["layout"] == "savings_plan":
        return build_savings_plan_tab(tab)
    if tab["layout"] == "earnings":
        return build_earnings_tab(tab)

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
# Significant digits rather than fixed decimals: crypto quantities and prices
# span from fractions of a cent / satoshi to tens of thousands.
_QUANTITY = Format(
    group=Group.yes,
    precision=6,
    scheme=Scheme.decimal_or_exponent,
    trim=Trim.yes,
)
# TERs are small (0.07 %), so two decimals.
_TER = Format(
    precision=2,
    scheme=Scheme.fixed,
    symbol=Symbol.yes,
    symbol_suffix=" %",
)
_PRICE = Format(
    group=Group.yes,
    precision=6,
    scheme=Scheme.decimal_or_exponent,
    trim=Trim.yes,
    symbol=Symbol.yes,
    symbol_suffix=" €",
)

_PORTFOLIO_TABLE_COLUMNS = [
    {"name": "Group", "id": "group"},
    {"name": "Name", "id": "name"},
    {"name": "Symbol", "id": "symbol"},
    {"name": "ISIN", "id": "isin"},
    {"name": "Depot / Exchange", "id": "exchange"},
    {"name": "Ccy", "id": "currency"},
    {
        "name": "Quantity",
        "id": "shares",
        "type": "numeric",
        "format": _QUANTITY,
    },
    {"name": "Price", "id": "price", "type": "numeric", "format": _PRICE},
    {
        "name": "Investment",
        "id": "investment",
        "type": "numeric",
        "format": _MONEY,
    },
    {"name": "Costs", "id": "costs", "type": "numeric", "format": _MONEY},
    {"name": "Value", "id": "value", "type": "numeric", "format": _MONEY},
    {"name": "Gain", "id": "gain", "type": "numeric", "format": _MONEY},
    {
        "name": "Gain %",
        "id": "gain_pct",
        "type": "numeric",
        "format": _PERCENT,
    },
    {
        "name": "Return p.a.",
        "id": "annual_return",
        "type": "numeric",
        "format": _PERCENT,
    },
    {"name": "TER", "id": "ter", "type": "numeric", "format": _TER},
    {
        "name": "Costs p.a.",
        "id": "cost_pa",
        "type": "numeric",
        "format": _MONEY,
    },
    {
        "name": "TER costs to date",
        "id": "ter_cost_to_date",
        "type": "numeric",
        "format": _MONEY,
    },
    {"name": "As of", "id": "as_of"},
]
_ANNUAL_RETURN_HINT = (
    "Money-weighted average annual return (XIRR): accounts for when each buy, "
    "sale and dividend happened, valuing what's still held at today's price. "
    "Blank for coins bought mostly by swapping other coins (no EUR price)."
)
_TER_HINT = (
    "Total expense ratio per year from the master data. Stocks, crypto and "
    "Riester have none (Riester's costs are the fees charged, in Costs)."
)
_COST_PA_HINT = "Ongoing costs per year at today's value: value × TER."
_TER_TO_DATE_HINT = (
    "Estimated ongoing costs (TER) since the position was bought: for every "
    "month held, the month-end value × TER / 12. Not a booking — the fund "
    "takes it out of its assets. Riester: 0, its fees are in Costs."
)


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
                    html.Span(
                        "  ·  Costs ",
                        style={"color": C["text_muted"], "fontSize": "13px"},
                    ),
                    html.Span(
                        f"{row['costs']:,.0f} €",
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
            _annual_return_line(row["annual_return"]),
            _ter_line(row["ter"], row["cost_pa"], row["ter_cost_to_date"]),
        ],
        flex="1",
        minWidth="230px",
    )


def _ter_line(ter: float, cost_pa: float, to_date: float) -> html.Div:
    """'TER Ø 0.21 %  ·  123 € p.a.  ·  760 € so far' ("No TER" for groups
    without one)."""
    muted = {"color": C["text_muted"], "fontSize": "13px"}
    if pd.isna(ter):
        return html.Div("No TER", style={**muted, "marginTop": "2px"})
    return html.Div(
        [
            html.Span("TER Ø ", style=muted),
            html.Span(
                f"{ter:.2f} %", style={"color": C["text"], "fontSize": "13px"}
            ),
            html.Span("  ·  ", style=muted),
            html.Span(
                f"{cost_pa:,.0f} €",
                style={"color": C["text"], "fontSize": "13px"},
            ),
            html.Span(" p.a.  ·  ", style=muted),
            html.Span(
                f"{to_date:,.0f} €",
                style={"color": C["text"], "fontSize": "13px"},
            ),
            html.Span(" so far", style=muted),
        ],
        title="Value-weighted average TER of the positions that have one, "
        "what they cost per year at today's value (value × TER), and the "
        "estimated ongoing costs since they were bought (on top of Costs).",
        style={"marginTop": "2px", "cursor": "help"},
    )


def _annual_return_line(annual_return: float) -> html.Div:
    """'+13.4 % per year' with the XIRR explained on hover."""
    if pd.isna(annual_return):
        text, color = "—", C["text_muted"]
    else:
        text = f"{annual_return:+.1f} %"
        color = C["positive"] if annual_return >= 0 else C["negative"]
    return html.Div(
        [
            html.Span(
                text,
                style={
                    "color": color,
                    "fontSize": "15px",
                    "fontWeight": "600",
                },
            ),
            html.Span(
                " per year",
                style={"color": C["text_muted"], "fontSize": "13px"},
            ),
        ],
        title=_ANNUAL_RETURN_HINT,
        style={"marginTop": "2px", "cursor": "help"},
    )


def build_portfolio_tab(tab: dict) -> dcc.Tab:
    agg = PORTFOLIO.group_aggregates()
    as_of = PORTFOLIO.as_of_by_group()

    cards = [_portfolio_group_card("Total Portfolio", agg.loc["All"], None)]
    for grp in GROUP_ORDER:
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
    _DropdownSpec("exchange", "Depot / Exchange", "220px"),
    _DropdownSpec("name", "Name", "380px", searchable=True),
]


def _portfolio_controls() -> html.Div:
    """Group/depot/name dropdowns, gainers/losers filter and reset button."""
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
    df = pd.DataFrame(
        rows,
        columns=["value", "investment", "costs", "gain", "cost_pa", "ter"],
    )
    value, invested, costs, gain, cost_pa = (
        pd.to_numeric(df[c], errors="coerce").sum()
        for c in ("value", "investment", "costs", "gain", "cost_pa")
    )
    ter = weighted_ter(
        pd.to_numeric(df["value"], errors="coerce"),
        pd.to_numeric(df["ter"], errors="coerce"),
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
        "  ·  Costs ",
        html.Span(f"{costs:,.0f} €", style=strong),
        "  ·  Gain ",
        html.Span(
            f"{gain:+,.0f} € ({pct:+.1f} %)",
            style={**strong, "color": gain_color},
        ),
        "  ·  TER Ø ",
        html.Span("—" if pd.isna(ter) else f"{ter:.2f} %", style=strong),
        "  ·  Costs p.a. ",
        html.Span(f"{cost_pa:,.0f} €", style=strong),
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
                "exchange",
                "currency",
                "as_of",
            )
        ],
        style_data_conditional=[
            {
                "if": {"filter_query": f"{{{col}}} {op} 0", "column_id": col},
                "color": color,
            }
            for col in ("gain", "gain_pct", "annual_return")
            for op, color in (("<", C["negative"]), (">=", C["positive"]))
        ],
        tooltip_header={
            "annual_return": _ANNUAL_RETURN_HINT,
            "ter": _TER_HINT,
            "cost_pa": _COST_PA_HINT,
            "ter_cost_to_date": _TER_TO_DATE_HINT,
        },
        tooltip_delay=300,
        tooltip_duration=None,
    )


# ---------------------------------------------------------------------------
# Allocation tab (breakdowns by attribute + TER / costs, per asset class)
# ---------------------------------------------------------------------------
_ALLOCATION_COLORS = {
    d.col: figures.allocation_colors(
        list(d.labels.values()),
        [b for b in d.order if b not in d.labels.values() and b != UNKNOWN],
    )
    for d in DIMENSIONS
}
_ALLOCATION_CLASSES = [
    c for c in ASSET_CLASSES if c in set(HOLDINGS["asset_class"])
]
_COSTS_TO_DATE_HINT = (
    "Order costs and fees paid (Costs in the Portfolio tab; Riester: its "
    "fees) plus the estimated ongoing costs (TER) since each position was "
    "bought: month-end value x TER / 12 for every month held."
)


def _allocation_controls() -> html.Div:
    counts = HOLDINGS["asset_class"].value_counts()
    return html.Div(
        [
            _control_label("Asset classes"),
            dcc.Checklist(
                id="allocation-classes",
                options=[
                    {"label": f" {c}  ({counts.get(c, 0)})", "value": c}
                    for c in _ALLOCATION_CLASSES
                ],
                value=list(_ALLOCATION_CLASSES),
                inline=True,
                inputStyle={"marginRight": "4px"},
                labelStyle={"marginRight": "18px", "cursor": "pointer"},
                style={"color": C["text"], "fontSize": "14px"},
            ),
            html.Button(
                "Select all",
                id="allocation-all",
                n_clicks=0,
                style={
                    "backgroundColor": C["background"],
                    "color": C["text"],
                    "border": f"1px solid {C['grid']}",
                    "borderRadius": "6px",
                    "padding": "4px 12px",
                    "cursor": "pointer",
                },
            ),
        ],
        style={"display": "flex", "flexWrap": "wrap", "alignItems": "center"},
    )


def _allocation_cost_kpis(holdings: pd.DataFrame) -> list[html.Div]:
    summary = cost_summary(holdings)
    n_funds = summary.n_with_ter
    ter_share = (
        summary.ter_value / summary.value * 100 if summary.value else 0.0
    )
    costs_to_date = _cash_kpi(
        "Costs to date",
        f"{summary.costs_to_date:,.0f} €",
        f"{summary.costs_paid:,.0f} € order costs & fees  +  "
        f"{summary.ter_cost_to_date:,.0f} € ongoing (est.)",
    )
    costs_to_date.title = _COSTS_TO_DATE_HINT
    return [
        _cash_kpi(
            "Value",
            f"{summary.value:,.0f} €",
            f"{summary.n_holdings} holdings",
        ),
        _cash_kpi(
            "Average TER",
            "—" if pd.isna(summary.ter) else f"{summary.ter:.2f} %",
            f"weighted by value over {n_funds} fund"
            f"{'s' if n_funds != 1 else ''} ({ter_share:.0f} % of the value)",
        ),
        _cash_kpi(
            "Ongoing costs p.a.",
            f"{summary.cost_pa:,.0f} €",
            f"value × TER  ·  {summary.cost_pa_pct:.2f} % of the whole value",
        ),
        costs_to_date,
    ]


def _swatch(color: str) -> html.Span:
    return html.Span(
        style={
            "display": "inline-block",
            "width": "10px",
            "height": "10px",
            "borderRadius": "2px",
            "backgroundColor": color,
            "marginRight": "8px",
        }
    )


def _breakdown_table(
    bd: pd.DataFrame,
    colors: dict[str, str],
    count_label: str = "Holdings",
    value_label: str = "Value",
) -> html.Table:
    cell = {"padding": "5px 8px", "borderBottom": f"1px solid {C['grid']}"}
    num = {**cell, "textAlign": "right", "whiteSpace": "nowrap"}
    head = {**num, "color": C["text_muted"], "fontWeight": "400"}
    header = html.Thead(
        html.Tr(
            [
                html.Th("", style=head),
                html.Th(count_label, style=head),
                html.Th(value_label, style=head),
                html.Th("Share", style=head),
            ]
        )
    )
    rows = []
    for r in bd.itertuples():
        rows.append(
            html.Tr(
                [
                    html.Td(
                        [_swatch(colors.get(r.bucket, C["grid"])), r.bucket],
                        style=cell,
                    ),
                    html.Td(str(r.n), style=num),
                    html.Td(f"{r.value:,.0f} €", style=num),
                    html.Td(f"{r.pct:.1f} %", style=num),
                ],
                title=", ".join(r.names),
            )
        )
    return html.Table(
        [header, html.Tbody(rows)],
        style={
            "borderCollapse": "collapse",
            "color": C["text"],
            "fontSize": "13px",
            "width": "100%",
        },
    )


def _breakdown_card(
    dim: Dimension,
    holdings: pd.DataFrame,
    count_label: str = "Holdings",
    value_label: str = "Value",
) -> html.Div:
    bd = breakdown(holdings, dim)
    colors = _ALLOCATION_COLORS[dim.col]
    return _card(
        [
            html.Div(
                dim.title,
                style={
                    "color": C["text"],
                    "fontSize": "15px",
                    "fontWeight": "600",
                    "marginBottom": "6px",
                },
            ),
            html.Div(
                [
                    html.Div(
                        dcc.Graph(
                            figure=figures.allocation_donut_figure(bd, colors),
                            config={"displayModeBar": False},
                        ),
                        style={"flex": "0 0 230px"},
                    ),
                    html.Div(
                        _breakdown_table(bd, colors, count_label, value_label),
                        style={"flex": "1", "minWidth": "240px"},
                    ),
                ],
                style={
                    "display": "flex",
                    "flexWrap": "wrap",
                    "alignItems": "center",
                    "gap": "8px",
                },
            ),
        ],
        flex="1 1 520px",
        minWidth="300px",
    )


# ---------------------------------------------------------------------------
# Monthly savings plan tab (the latest execution of the ETF savings plan)
# ---------------------------------------------------------------------------
_PLAN_DIMENSIONS = [
    DIMENSION_BY_COL["region"],
    DIMENSION_BY_COL["distribution"],
]
_PLAN_TABLE_COLUMNS = [
    {"name": "ETF", "id": "name"},
    {"name": "ISIN", "id": "isin"},
    {"name": "Depot", "id": "depot"},
    {"name": "Amount", "id": "amount", "type": "numeric", "format": _MONEY},
    {"name": "Share", "id": "share", "type": "numeric", "format": _PERCENT},
    {"name": "Price", "id": "price", "type": "numeric", "format": _PRICE},
    {"name": "Shares", "id": "shares", "type": "numeric", "format": _QUANTITY},
    {"name": "TER", "id": "ter", "type": "numeric", "format": _TER},
    {"name": "Region", "id": "region_label"},
    {"name": "Acc / Dist", "id": "distribution_label"},
    {"name": "Executed", "id": "date"},
]


def _plan_kpis(plan: SavingsPlan) -> html.Div:
    n = len(plan.buys)
    return html.Div(
        [
            _cash_kpi(
                "Monthly amount",
                f"{plan.amount:,.2f} €",
                f"{n} ETF{'s' if n != 1 else ''}  ·  execution #{plan.execution}"
                f"  ·  {plan.date_label}",
            ),
            _cash_kpi(
                "Per year",
                f"{plan.amount * 12:,.0f} €",
                "12 × the latest execution",
            ),
            _cash_kpi(
                "Average TER",
                "—" if pd.isna(plan.ter) else f"{plan.ter:.2f} %",
                "weighted by the amount per ETF",
            ),
            _cash_kpi(
                "Order costs",
                f"{plan.costs:,.2f} €",
                "of this execution",
            ),
        ],
        style={"display": "flex", "flexWrap": "wrap"},
    )


def _plan_records(plan: SavingsPlan) -> list[dict]:
    buys = plan.buys.copy()
    for dim in _PLAN_DIMENSIONS:
        buys[f"{dim.col}_label"] = [
            dim.bucket("ETFs", raw) for raw in buys[dim.col]
        ]
    buys["date"] = buys["date"].dt.strftime("%Y-%m-%d")
    return buys.to_dict("records")


def _plan_table(plan: SavingsPlan) -> html.Div:
    table = dash_table.DataTable(
        id="savings-plan-table",
        columns=_PLAN_TABLE_COLUMNS,
        data=_plan_records(plan),
        sort_action="native",
        style_as_list_view=True,
        style_table={"overflowX": "auto"},
        style_header=_TABLE_HEADER_STYLE,
        style_cell=_TABLE_CELL_STYLE,
        style_cell_conditional=[
            {"if": {"column_id": c}, "textAlign": "left"}
            for c in (
                "name",
                "isin",
                "depot",
                "region_label",
                "distribution_label",
                "date",
            )
        ],
    )
    return _card(
        [
            html.Div(
                "Which ETFs the plan buys",
                style={
                    "color": C["text"],
                    "fontSize": "15px",
                    "fontWeight": "600",
                    "marginBottom": "10px",
                },
            ),
            table,
        ]
    )


def build_savings_plan_tab(tab: dict) -> dcc.Tab:
    if SAVINGS_PLAN is None:
        body = [
            _card(
                "No savings plan found. Run the datahub to create "
                "transform_etf__savings_plan.csv from the Buys sheet.",
                color=C["text_muted"],
            )
        ]
        return _tab_shell(tab["label"], tab["kind"], body)
    holdings = SAVINGS_PLAN.as_holdings()
    cards = html.Div(
        [
            _breakdown_card(
                d, holdings, count_label="ETFs", value_label="Amount"
            )
            for d in _PLAN_DIMENSIONS
        ],
        style={"display": "flex", "flexWrap": "wrap"},
    )
    note = html.Div(
        "The latest execution of the savings plan: every buy with the highest "
        "index of the Buys sheet. The splits are by amount invested; hover a "
        "slice or row to see its ETFs.",
        style={
            "color": C["text_muted"],
            "fontSize": "12px",
            "margin": "0 10px 10px",
        },
    )
    return _tab_shell(
        tab["label"],
        tab["kind"],
        [_plan_kpis(SAVINGS_PLAN), _plan_table(SAVINGS_PLAN), cards, note],
    )


# ---------------------------------------------------------------------------
# Earnings tab (dividends and interest per year and holding)
# ---------------------------------------------------------------------------
_EARNINGS_STACK_OPTIONS = [
    {"label": "Type", "value": "type"},
    {"label": "Holding", "value": "holding"},
]
_DIVIDEND_TYPE_LABELS = {"ETF dividends": "ETF", "Stock dividends": "Stock"}


def _earnings_year_label(year: int) -> str:
    if EARNINGS is not None and year == EARNINGS.current_year:
        return f"{year} YTD"
    return str(year)


def _earnings_change(current: float, previous: float, year: int) -> str:
    if not previous:
        return f"nothing by this date in {year}"
    pct = (current / previous - 1) * 100
    return f"{pct:+.0f} % vs {previous:,.2f} € by this date in {year}"


def _earnings_kpis(earnings: EarningsData, today: pd.Timestamp) -> html.Div:
    year = earnings.current_year
    current = earnings.total(year)
    previous = earnings.total(year - 1, until=today - pd.DateOffset(years=1))
    dividends = earnings.total(year, KIND_DIVIDEND)
    n_paying = len(earnings.in_year(year, KIND_DIVIDEND))
    interest = earnings.total(year, KIND_INTEREST)
    return html.Div(
        [
            _cash_kpi(
                f"Earnings {year}",
                f"{current:,.2f} €",
                _earnings_change(current, previous, year - 1),
                color=C["positive"],
            ),
            _cash_kpi(
                f"Dividends {year}",
                f"{dividends:,.2f} €",
                f"from {n_paying} holding{'s' if n_paying != 1 else ''}",
            ),
            _cash_kpi(
                f"Interest {year}",
                f"{interest:,.2f} €",
                "Tagesgeld and Festgeld",
            ),
            _cash_kpi(
                "All-time earnings",
                f"{earnings.total():,.2f} €",
                f"since {earnings.years[0]}  ·  "
                f"{earnings.total(kind=KIND_DIVIDEND):,.0f} € dividends, "
                f"{earnings.total(kind=KIND_INTEREST):,.0f} € interest",
            ),
        ],
        style={"display": "flex", "flexWrap": "wrap"},
    )


def _earnings_yearly_card(earnings: EarningsData) -> html.Div:
    years = earnings.years
    return _card(
        [
            _section_title("Earnings per year"),
            html.Div(
                [
                    _control_label("Stack by:"),
                    _radio("earnings-stack", _EARNINGS_STACK_OPTIONS, "type"),
                    html.Span(
                        "Click a bar to break that year down by holding",
                        style={
                            "color": C["text_muted"],
                            "fontSize": "12px",
                            "float": "right",
                        },
                    ),
                ],
                style={"marginBottom": "16px"},
            ),
            dcc.RangeSlider(
                id="earnings-years",
                min=years[0],
                max=years[-1],
                step=1,
                value=[years[0], years[-1]],
                marks={
                    y: {"label": str(y), "style": {"color": C["text_muted"]}}
                    for y in years
                },
                allowCross=False,
            ),
            dcc.Graph(id="earnings-yearly-graph"),
        ]
    )


def _dividends_ranking_figure(earnings: EarningsData):
    year = earnings.current_year
    rows = earnings.in_year(year, KIND_DIVIDEND)
    previous = earnings.in_year(year - 1, KIND_DIVIDEND).set_index("holding")[
        "amount"
    ]
    return figures.earnings_holdings_figure(
        rows,
        earnings.holding_colors,
        title=(
            f"Dividends {_earnings_year_label(year)} per holding: "
            f"<b>{rows['amount'].sum():,.2f} €</b>"
        ),
        empty_message=f"No dividends in {year} yet",
        previous=previous,
    )


def _dividends_table_records(earnings: EarningsData) -> list[dict]:
    year = earnings.current_year
    matrix = earnings.yearly_by_holding(KIND_DIVIDEND).T  # holding x year
    info = earnings.holdings()
    matrix["total"] = matrix.sum(axis=1)
    matrix = matrix.sort_values([year, "total"], ascending=False)
    records = []
    for holding, row in matrix.iterrows():
        record = {
            "name": info.at[holding, "name"],
            "type": _DIVIDEND_TYPE_LABELS.get(info.at[holding, "type"], ""),
            "total": row["total"],
        }
        # empty instead of 0,00 € in years without a dividend
        record.update(
            {str(y): (row[y] if row[y] else None) for y in earnings.years}
        )
        records.append(record)
    totals = {"name": "Total", "type": "", "total": matrix["total"].sum()}
    totals.update({str(y): matrix[y].sum() for y in earnings.years})
    records.append(totals)
    return records


def _dividends_table_card(earnings: EarningsData) -> html.Div:
    year = earnings.current_year
    records = _dividends_table_records(earnings)
    columns = [
        {"name": "Holding", "id": "name"},
        {"name": "Type", "id": "type"},
    ]
    columns += [
        {
            "name": _earnings_year_label(y),
            "id": str(y),
            "type": "numeric",
            "format": _MONEY,
        }
        for y in earnings.years
    ]
    columns.append(
        {"name": "Total", "id": "total", "type": "numeric", "format": _MONEY}
    )
    table = dash_table.DataTable(
        id="earnings-dividends-table",
        columns=columns,
        data=records,
        style_as_list_view=True,
        style_table={"overflowX": "auto"},
        style_header=_TABLE_HEADER_STYLE,
        style_cell=_TABLE_CELL_STYLE,
        style_cell_conditional=[
            {"if": {"column_id": c}, "textAlign": "left"}
            for c in ("name", "type")
        ],
        style_data_conditional=[
            {
                "if": {"column_id": str(year)},
                "color": C["income"],
                "fontWeight": "600",
            },
            {"if": {"column_id": "total"}, "fontWeight": "600"},
            {
                "if": {"filter_query": '{name} = "Total"'},
                "fontWeight": "700",
                "backgroundColor": C["background"],
            },
        ],
        tooltip_data=[
            {"name": {"value": r["name"], "type": "text"}} for r in records
        ],
        tooltip_delay=400,
        tooltip_duration=None,
    )
    return _card(
        [
            _section_title("Dividends per holding and year"),
            html.Div(
                f"Ordered by the dividends of {_earnings_year_label(year)}, "
                "then by the total; sold holdings stay listed.",
                style={
                    "color": C["text_muted"],
                    "fontSize": "12px",
                    "marginBottom": "10px",
                },
            ),
            table,
        ]
    )


def build_earnings_tab(tab: dict) -> dcc.Tab:
    if EARNINGS is None:
        body = [
            _card(
                "No earnings found. Run the datahub to create "
                "transform_portfolio__earnings.csv from the Dividends and "
                "Zinsen sheets.",
                color=C["text_muted"],
            )
        ]
        return _tab_shell(tab["label"], tab["kind"], body)
    detail_row = html.Div(
        [
            html.Div(
                _card(dcc.Graph(id="earnings-year-graph")),
                style={"flex": "1", "minWidth": "420px"},
            ),
            html.Div(
                _card(
                    dcc.Graph(
                        id="earnings-dividends-graph",
                        figure=_dividends_ranking_figure(EARNINGS),
                    )
                ),
                style={"flex": "1", "minWidth": "420px"},
            ),
        ],
        style={
            "display": "flex",
            "flexWrap": "wrap",
            "alignItems": "flex-start",
        },
    )
    note = html.Div(
        "Dividends count when paid out (ETF distributions and stock "
        "dividends, sold holdings included); interest when credited to the "
        "Tagesgeld or Festgeld account. The running year counts every "
        "payment so far.",
        style={
            "color": C["text_muted"],
            "fontSize": "12px",
            "margin": "0 10px 10px",
        },
    )
    return _tab_shell(
        tab["label"],
        tab["kind"],
        [
            _earnings_kpis(EARNINGS, pd.Timestamp.today().normalize()),
            _earnings_yearly_card(EARNINGS),
            detail_row,
            _dividends_table_card(EARNINGS),
            note,
            dcc.Store(id="earnings-selected-year", data=EARNINGS.current_year),
        ],
    )


def _clicked_year(click_data) -> int | None:
    """The year of a clicked bar (its tick reads "2025" or "2026 YTD")."""
    try:
        return int(str(click_data["points"][0]["x"])[:4])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _register_earnings_callbacks() -> None:
    if EARNINGS is None:
        return

    @app.callback(
        Output("earnings-selected-year", "data"),
        Input("earnings-yearly-graph", "clickData"),
        prevent_initial_call=True,
    )
    def _select_year(click_data):
        year = _clicked_year(click_data)
        return no_update if year is None else year

    @app.callback(
        Output("earnings-yearly-graph", "figure"),
        Output("earnings-year-graph", "figure"),
        Input("earnings-years", "value"),
        Input("earnings-stack", "value"),
        Input("earnings-selected-year", "data"),
    )
    def _update_earnings(years_range, stack_by, selected):
        all_years = EARNINGS.years
        start, end = sorted(years_range or [all_years[0], all_years[-1]])
        years = [y for y in all_years if start <= y <= end]
        # a year outside the slider range falls back to the latest one shown
        if selected not in years:
            selected = years[-1] if years else None
        yearly = figures.earnings_yearly_figure(
            EARNINGS, years, stack_by or "type", selected
        )
        if selected is None:
            return yearly, figures._empty("No year selected")
        rows = EARNINGS.in_year(selected)
        previous = EARNINGS.in_year(selected - 1).set_index("holding")[
            "amount"
        ]
        breakdown = figures.earnings_holdings_figure(
            rows,
            EARNINGS.holding_colors,
            title=(
                f"Earnings {_earnings_year_label(selected)} by holding: "
                f"<b>{rows['amount'].sum():,.2f} €</b>"
            ),
            empty_message=f"No earnings in {selected}",
            previous=previous,
        )
        return yearly, breakdown


def _allocation_body(classes: list[str] | None) -> list:
    holdings = select(HOLDINGS, classes)
    if not classes or holdings.empty:
        return [_card("Tick at least one asset class.", color=C["text_muted"])]
    kpis = html.Div(
        _allocation_cost_kpis(holdings),
        style={"display": "flex", "flexWrap": "wrap"},
    )
    cards = html.Div(
        [_breakdown_card(d, holdings) for d in DIMENSIONS],
        style={"display": "flex", "flexWrap": "wrap"},
    )
    note = html.Div(
        "Every split adds up to 100 % of the selected value. Grey slices are "
        "asset classes the split doesn't apply to; Unknown means the master "
        "data has no value yet (datahub source_etf__master_data.csv). Hover a "
        "slice or row to see its holdings.",
        style={
            "color": C["text_muted"],
            "fontSize": "12px",
            "margin": "0 10px 10px",
        },
    )
    return [kpis, cards, note]


def build_allocation_tab(tab: dict) -> dcc.Tab:
    controls = _card([_allocation_controls()])
    body = html.Div(
        _allocation_body(list(_ALLOCATION_CLASSES)), id="allocation-body"
    )
    return _tab_shell(tab["label"], tab["kind"], [controls, body])


def _register_allocation_callbacks() -> None:
    @app.callback(
        Output("allocation-classes", "value"),
        Input("allocation-all", "n_clicks"),
        prevent_initial_call=True,
    )
    def _select_all(_n):
        return list(_ALLOCATION_CLASSES)

    @app.callback(
        Output("allocation-body", "children"),
        Input("allocation-classes", "value"),
        prevent_initial_call=True,
    )
    def _update(classes):
        return _allocation_body(classes)


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


# ---------------------------------------------------------------------------
# Sold Positions tab (sold ETF/stock positions + KPI cards + cashflow drill-down)
# ---------------------------------------------------------------------------
_SOLD_ROI_HINT = (
    "Net profit / buy amount. Net profit = sell proceeds + dividends − buy "
    "amount − order costs − ongoing costs."
)
_SOLD_ANNUAL_HINT = (
    "Money-weighted average annual return (XIRR) of the position's buys, "
    "sells, dividends and costs: accounts for how long each euro was invested."
)
_SOLD_TABLE_COLUMNS = [
    {"name": "Group", "id": "group"},
    {"name": "Name", "id": "name"},
    {"name": "ISIN", "id": "isin"},
    {"name": "Depot", "id": "exchange"},
    {"name": "First buy", "id": "open_date", "type": "datetime"},
    {"name": "Sold", "id": "close_date", "type": "datetime"},
    {"name": "Days held", "id": "holding_days", "type": "numeric"},
    {
        "name": "Shares",
        "id": "shares_bought",
        "type": "numeric",
        "format": _QUANTITY,
    },
    {
        "name": "Bought for",
        "id": "buy_amount",
        "type": "numeric",
        "format": _MONEY,
    },
    {
        "name": "Sold for",
        "id": "sell_amount",
        "type": "numeric",
        "format": _MONEY,
    },
    {
        "name": "Price gain",
        "id": "price_gain",
        "type": "numeric",
        "format": _MONEY,
    },
    {
        "name": "Dividends",
        "id": "dividends",
        "type": "numeric",
        "format": _MONEY,
    },
    {
        "name": "Order costs",
        "id": "order_costs",
        "type": "numeric",
        "format": _MONEY,
    },
    {
        "name": "Ongoing costs",
        "id": "ongoing_costs",
        "type": "numeric",
        "format": _MONEY,
    },
    {
        "name": "Net profit",
        "id": "net_profit",
        "type": "numeric",
        "format": _MONEY,
    },
    {"name": "ROI", "id": "roi_pct", "type": "numeric", "format": _PERCENT},
    {
        "name": "Return p.a.",
        "id": "annual_return_pct",
        "type": "numeric",
        "format": _PERCENT,
    },
    {"name": "Bought again", "id": "rebought"},
]
_SOLD_LEFT_COLUMNS = (
    "group",
    "name",
    "isin",
    "exchange",
    "open_date",
    "close_date",
    "rebought",
)
_SOLD_DROPDOWNS = [
    _DropdownSpec("group", "Group", "170px"),
    _DropdownSpec("exchange", "Depot", "200px"),
    _DropdownSpec("sold_year", "Year sold", "170px"),
    _DropdownSpec("name", "Name", "380px", searchable=True),
]


def _sold_records() -> pd.DataFrame:
    records = SOLD.positions.copy()
    for col in ("open_date", "close_date"):
        records[col] = records[col].dt.strftime("%Y-%m-%d")
    return records


_SOLD_RECORDS = _sold_records()


def _signed_color(amount: float) -> str:
    return C["positive"] if amount >= 0 else C["negative"]


def _pct_span(value: float, size: str = "15px", **attrs) -> html.Span:
    """'+5.4 %' in green/red, or a muted '—' when there is no value."""
    missing = pd.isna(value)
    return html.Span(
        "—" if missing else f"{value:+.1f} %",
        style={
            "color": C["text_muted"] if missing else _signed_color(value),
            "fontSize": size,
            "fontWeight": "600",
        },
        **attrs,
    )


def _sold_group_card(title: str, row: pd.Series, subtitle: str) -> html.Div:
    profit = float(row["net_profit"])
    muted = {"color": C["text_muted"], "fontSize": "13px"}
    plain = {"color": C["text"], "fontSize": "13px"}

    def line(*parts, **style):
        return html.Div(list(parts), style={"marginTop": "3px", **style})

    return _card(
        [
            html.Div(
                title, style={"color": C["text_muted"], "fontSize": "15px"}
            ),
            html.Div(
                subtitle,
                style={"color": C["text_muted"], "fontSize": "12px"},
            ),
            html.Div(
                f"{profit:+,.0f} €",
                title="Net profit after all costs",
                style={
                    "color": _signed_color(profit),
                    "fontSize": "30px",
                    "fontWeight": "600",
                    "marginTop": "6px",
                },
            ),
            line(
                _pct_span(row["roi_pct"]),
                html.Span(" ROI  ·  ", style=muted),
                _pct_span(row["annual_return_pct"], title=_SOLD_ANNUAL_HINT),
                html.Span(" per year", style=muted),
                title=_SOLD_ROI_HINT,
            ),
            line(
                html.Span("Bought for ", style=muted),
                html.Span(f"{row['buy_amount']:,.0f} €", style=plain),
                html.Span("  ·  Sold for ", style=muted),
                html.Span(f"{row['sell_amount']:,.0f} €", style=plain),
                marginTop="8px",
            ),
            line(
                html.Span("Dividends ", style=muted),
                html.Span(f"+{row['dividends']:,.0f} €", style=plain),
                html.Span("  ·  Costs ", style=muted),
                html.Span(f"−{row['total_costs']:,.0f} €", style=plain),
            ),
        ],
        flex="1",
        minWidth="250px",
    )


def _sold_controls() -> html.Div:
    performance = _labelled_control(
        "Show",
        _radio(
            "sold-performance",
            [
                {"label": "All", "value": "all"},
                {"label": "Gainers", "value": "gain"},
                {"label": "Losers", "value": "loss"},
            ],
            "all",
        ),
        "auto",
    )
    rebought = _labelled_control(
        "Bought again later",
        _radio(
            "sold-rebought",
            [
                {"label": "All", "value": "all"},
                {"label": "No (exited)", "value": "No"},
                {"label": "Yes", "value": "Yes"},
            ],
            "all",
        ),
        "auto",
    )
    return _filter_controls(
        "sold",
        _SOLD_RECORDS,
        _SOLD_DROPDOWNS,
        extra=[performance, rebought],
        hint="; click a position to list its cashflows",
    )


def _filter_sold(
    selections: dict[str, list],
    performance: str,
    rebought: str,
    skip: str | None = None,
) -> pd.DataFrame:
    df = _filter_by_dropdowns(_SOLD_RECORDS, selections, skip)
    if performance == "gain":
        df = df[df["net_profit"] > 0]
    elif performance == "loss":
        df = df[df["net_profit"] < 0]
    if rebought in ("Yes", "No"):
        df = df[df["rebought"] == rebought]
    return df


def _sold_summary(rows: list[dict] | None) -> list:
    ids = [r["id"] for r in rows or []]
    totals = SOLD.aggregate(SOLD.positions[SOLD.positions["id"].isin(ids)])
    strong = {"color": C["text"], "fontWeight": "600"}
    profit, roi = totals["net_profit"], totals["roi_pct"]
    roi_text = "" if pd.isna(roi) else f" ({roi:+.1f} %)"
    return [
        html.Span(
            f"{len(ids)} of {len(_SOLD_RECORDS)} sold positions", style=strong
        ),
        "  ·  Bought for ",
        html.Span(f"{totals['buy_amount']:,.0f} €", style=strong),
        "  ·  Sold for ",
        html.Span(f"{totals['sell_amount']:,.0f} €", style=strong),
        "  ·  Dividends ",
        html.Span(f"{totals['dividends']:,.0f} €", style=strong),
        "  ·  Costs ",
        html.Span(f"{totals['total_costs']:,.0f} €", style=strong),
        "  ·  Net profit ",
        html.Span(
            f"{profit:+,.0f} €{roi_text}",
            style={**strong, "color": _signed_color(profit)},
        ),
    ]


_TABLE_HEADER_STYLE = {
    "backgroundColor": C["background"],
    "color": C["text"],
    "fontWeight": "600",
    "border": "none",
    "borderBottom": f"2px solid {C['grid']}",
}
_TABLE_CELL_STYLE = {
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
}


def _sold_table() -> dash_table.DataTable:
    return dash_table.DataTable(
        id="sold-table",
        columns=_SOLD_TABLE_COLUMNS,
        data=_SOLD_RECORDS.to_dict("records"),
        sort_action="native",
        sort_by=[],
        page_size=40,
        style_as_list_view=True,
        style_table={"overflowX": "auto"},
        style_header=_TABLE_HEADER_STYLE,
        style_cell=_TABLE_CELL_STYLE,
        style_cell_conditional=[
            {"if": {"column_id": c}, "textAlign": "left"}
            for c in _SOLD_LEFT_COLUMNS
        ],
        style_data_conditional=[
            {
                "if": {"filter_query": f"{{{col}}} {op} 0", "column_id": col},
                "color": color,
            }
            for col in (
                "price_gain",
                "net_profit",
                "roi_pct",
                "annual_return_pct",
            )
            for op, color in (("<", C["negative"]), (">=", C["positive"]))
        ]
        + [
            {
                "if": {"state": "active"},
                "backgroundColor": C["grid"],
                "border": f"1px solid {C['average']}",
            }
        ],
        tooltip_header={
            "roi_pct": _SOLD_ROI_HINT,
            "annual_return_pct": _SOLD_ANNUAL_HINT,
            "ongoing_costs": "Yearly per-security costs (e.g. comdirect "
            "Wertpapierkosten), split by the days held in each year.",
            "rebought": "The security was bought again after this sale "
            "(e.g. sold and re-bought to use the tax-free allowance).",
        },
        tooltip_delay=300,
        tooltip_duration=None,
    )


def _sold_flows_card() -> html.Div:
    return _card(
        [
            html.Div(
                "Click a position above to list its cashflows",
                id="sold-flows-title",
                style={
                    "color": C["text"],
                    "fontSize": "15px",
                    "fontWeight": "600",
                    "marginBottom": "10px",
                },
            ),
            dash_table.DataTable(
                id="sold-flows-table",
                columns=[
                    {"name": "Date", "id": "date"},
                    {"name": "Type", "id": "type"},
                    {
                        "name": "Amount",
                        "id": "amount",
                        "type": "numeric",
                        "format": _MONEY,
                    },
                ],
                data=[],
                sort_action="native",
                page_size=20,
                style_as_list_view=True,
                style_table={"overflowX": "auto", "maxWidth": "640px"},
                style_header=_TABLE_HEADER_STYLE,
                style_cell=_TABLE_CELL_STYLE,
                style_cell_conditional=[
                    {"if": {"column_id": c}, "textAlign": "left"}
                    for c in ("date", "type")
                ],
                style_data_conditional=[
                    {
                        "if": {
                            "filter_query": f"{{amount}} {op} 0",
                            "column_id": "amount",
                        },
                        "color": color,
                    }
                    for op, color in (
                        ("<", C["negative"]),
                        (">=", C["positive"]),
                    )
                ],
            ),
        ]
    )


def _sold_kpi_cards(rows: list[dict] | None) -> list[html.Div]:
    """KPI cards (all + per group) of the positions left by the table
    filters; ``rows`` None means unfiltered."""
    ids = None if rows is None else [r["id"] for r in rows]
    agg = SOLD.group_aggregates(ids)
    total = len(_SOLD_RECORDS)
    filtered = ids is not None and len(ids) < total

    def subtitle(n: int) -> str:
        return f"{n} positions sold" + ("  ·  filtered" if filtered else "")

    all_row = agg.loc["All"]
    cards = [
        _sold_group_card(
            "Filtered sold positions" if filtered else "All sold positions",
            all_row,
            f"{int(all_row['n_positions'])} of {total} positions"
            if filtered
            else subtitle(total),
        )
    ]
    for grp in SOLD_GROUP_ORDER:
        if grp in agg.index:
            row = agg.loc[grp]
            cards.append(
                _sold_group_card(grp, row, subtitle(int(row["n_positions"])))
            )
    return cards


def build_sold_tab(tab: dict) -> dcc.Tab:
    kpi_row = html.Div(
        _sold_kpi_cards(None),
        id="sold-kpis",
        style={"display": "flex", "flexWrap": "wrap"},
    )

    table = _card(
        [
            _sold_controls(),
            html.Div(
                id="sold-summary",
                style={
                    "color": C["text_muted"],
                    "fontSize": "13px",
                    "margin": "12px 0 8px",
                },
            ),
            _sold_table(),
        ]
    )
    return _tab_shell(
        tab["label"], tab["kind"], [kpi_row, table, _sold_flows_card()]
    )


def _register_sold_callbacks() -> None:
    _register_filter_callbacks(
        "sold",
        _SOLD_DROPDOWNS,
        _filter_sold,
        extra_inputs={"sold-performance": "all", "sold-rebought": "all"},
    )

    # Summary line and KPI cards of exactly what is visible after all
    # filters (all pages).
    @app.callback(
        Output("sold-summary", "children"),
        Output("sold-kpis", "children"),
        Input("sold-table", "derived_virtual_data"),
    )
    def _update_summary(rows):
        return _sold_summary(rows), _sold_kpi_cards(rows)

    # Clicking any cell of a position lists that position's cashflows.
    @app.callback(
        Output("sold-flows-title", "children"),
        Output("sold-flows-table", "data"),
        Input("sold-table", "active_cell"),
    )
    def _update_flows(active_cell):
        position_id = (active_cell or {}).get("row_id")
        match = SOLD.positions[SOLD.positions["id"] == position_id]
        if match.empty:
            return "Click a position above to list its cashflows", []
        position = match.iloc[0]
        flows = SOLD.position_flows(position_id)
        records = pd.DataFrame(
            {
                "date": flows["date"].dt.strftime("%Y-%m-%d"),
                "type": flows["type"],
                "amount": flows["amount"],
            }
        ).to_dict("records")
        profit = position["net_profit"]
        title = (
            f"{position['name']}  ·  {position['open_date']:%d %b %Y} – "
            f"{position['close_date']:%d %b %Y}  ·  net profit {profit:+,.2f} € "
            f"({len(records)} cashflows)"
        )
        return title, records


# ---------------------------------------------------------------------------
# Cash tab (account balances, fixed-term deposits, available vs. bound cash)
# ---------------------------------------------------------------------------
_RATE = Format(precision=2, scheme=Scheme.percentage)
_STALE_SUFFIX = "  (outdated)"

_CASH_ACCOUNT_COLUMNS = [
    {"name": "Account", "id": "name"},
    {"name": "Bank", "id": "bank"},
    {"name": "Platform", "id": "platform"},
    {"name": "Type", "id": "type"},
    {"name": "Balance", "id": "balance", "type": "numeric", "format": _MONEY},
    {"name": "Interest", "id": "rate_pa", "type": "numeric", "format": _RATE},
    {"name": "Rate valid until", "id": "rate_valid_until"},
    {"name": "Balance as of", "id": "balance_date"},
]
_CASH_DEPOSIT_COLUMNS = [
    {"name": "Bank", "id": "bank"},
    {"name": "Platform", "id": "platform"},
    {"name": "Name", "id": "name"},
    {"name": "Amount", "id": "principal", "type": "numeric", "format": _MONEY},
    {"name": "Interest", "id": "rate_pa", "type": "numeric", "format": _RATE},
    {"name": "Start", "id": "start_date"},
    {"name": "End", "id": "end_date"},
    {"name": "Days left", "id": "days_remaining", "type": "numeric"},
    {
        "name": "Progress",
        "id": "progress_pct",
        "type": "numeric",
        "format": _PERCENT,
    },
    {"name": "Status", "id": "status"},
]
_CASH_TEXT_COLUMNS = (
    "name",
    "bank",
    "platform",
    "type",
    "rate_valid_until",
    "balance_date",
    "start_date",
    "end_date",
    "status",
)


def _cash_table(
    table_id: str, columns: list, records: list, extra_styles: list
):
    return dash_table.DataTable(
        id=table_id,
        columns=columns,
        data=records,
        sort_action="native",
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
            for c in _CASH_TEXT_COLUMNS
        ],
        style_data_conditional=extra_styles,
    )


def _iso(values: pd.Series) -> pd.Series:
    return values.dt.strftime("%Y-%m-%d").fillna("")


def _cash_account_records(accounts: pd.DataFrame) -> list[dict]:
    df = accounts.copy()
    df["platform"] = df["platform"].fillna("")
    df["rate_valid_until"] = _iso(df["rate_valid_until"])
    df["balance_date"] = _iso(df["balance_date"]) + df["is_stale"].map(
        {True: _STALE_SUFFIX, False: ""}
    )
    return df[[c["id"] for c in _CASH_ACCOUNT_COLUMNS]].to_dict("records")


def _cash_deposit_records(cash: CashData) -> list[dict]:
    df = cash.deposits.copy()
    df["platform"] = df["platform"].fillna("")
    df["start_date"] = _iso(df["start_date"])
    df["end_date"] = _iso(df["end_date"])
    df["status"] = df["status"].map(STATUS_LABELS).fillna(df["status"])
    return df[[c["id"] for c in _CASH_DEPOSIT_COLUMNS]].to_dict("records")


def _progress_bar_styles(progress: pd.Series) -> list[dict]:
    """A data bar behind every progress value (tables cannot draw bars)."""
    styles = []
    for pct in sorted(set(progress.dropna())):
        styles.append(
            {
                "if": {
                    "filter_query": f"{{progress_pct}} = {pct}",
                    "column_id": "progress_pct",
                },
                "background": (
                    f"linear-gradient(90deg, {C['cash_bound']}66 0%, "
                    f"{C['cash_bound']}66 {pct}%, transparent {pct}%, "
                    "transparent 100%)"
                ),
            }
        )
    return styles


def _cash_kpi(title: str, value: str, subtitle: str, color: str | None = None):
    return _card(
        [
            html.Div(
                title, style={"color": C["text_muted"], "fontSize": "15px"}
            ),
            html.Div(
                value,
                style={
                    "color": color or C["text"],
                    "fontSize": "30px",
                    "fontWeight": "600",
                    "marginTop": "6px",
                },
            ),
            html.Div(
                subtitle,
                style={
                    "color": C["text_muted"],
                    "fontSize": "13px",
                    "marginTop": "4px",
                },
            ),
        ],
        flex="1",
        minWidth="200px",
    )


def _cash_kpis(cash: CashData, today: pd.Timestamp) -> html.Div:
    available, bound, owed = cash.available, cash.bound, cash.owed
    as_of = cash.as_of
    n_running = len(cash.running_deposits)
    n_liabilities = len(cash.liabilities)
    cards = [
        _cash_kpi(
            "Net cash",
            f"{cash.net:,.0f} €",
            f"{available + bound:,.0f} € cash − {abs(owed):,.0f} € owed"
            + (f"  ·  as of {as_of:%d %b %Y}" if as_of is not None else ""),
        ),
        _cash_kpi(
            "Available",
            f"{available:,.0f} €",
            f"on {len(cash.accounts)} accounts",
            C["cash_available"],
        ),
        _cash_kpi(
            "Bound",
            f"{bound:,.0f} €",
            f"in {n_running} fixed-term deposit{'s' if n_running != 1 else ''}",
            C["cash_bound"],
        ),
        _cash_kpi(
            "Liabilities",
            f"{abs(owed):,.0f} €",
            f"on {n_liabilities} credit card / loan account"
            + ("s" if n_liabilities != 1 else ""),
            C["negative"] if owed < 0 else None,
        ),
    ]
    nxt = cash.next_maturity()
    if nxt is not None:
        days = (nxt["end_date"] - today).days
        cards.append(
            _cash_kpi(
                "Next maturity",
                f"{nxt['principal']:,.0f} €",
                f"{nxt['bank']}  ·  {nxt['end_date']:%d %b %Y}  ·  in {days} days",
            )
        )
    rate = cash.weighted_rate()
    cards.append(
        _cash_kpi(
            "Average interest rate",
            "—" if pd.isna(rate) else f"{rate * 100:.2f} %",
            "of all cash, weighted by amount",
        )
    )
    return html.Div(cards, style={"display": "flex", "flexWrap": "wrap"})


def build_cash_tab(tab: dict) -> dcc.Tab:
    if CASH is None:
        body = [
            _card(
                "No cash data found. Run the datahub to create the "
                "transform_cash__* tables from source_cash_balance_sheet.ods.",
                color=C["text_muted"],
            )
        ]
        return _tab_shell(tab["label"], tab["kind"], body)

    today = pd.Timestamp.today().normalize()
    open_deposits = CASH.deposits[CASH.deposits["status"] != STATUS_MATURED]
    stale_style = [
        {
            "if": {
                "filter_query": f'{{balance_date}} contains "{_STALE_SUFFIX.strip()}"',
                "column_id": "balance_date",
            },
            "color": C["negative"],
        }
    ]
    accounts = _card(
        [
            _section_title("Accounts"),
            _cash_table(
                "cash-accounts-table",
                _CASH_ACCOUNT_COLUMNS,
                _cash_account_records(CASH.accounts),
                stale_style,
            ),
        ]
    )
    liabilities = _card(
        [
            _section_title("Liabilities"),
            _cash_table(
                "cash-liabilities-table",
                _CASH_ACCOUNT_COLUMNS,
                _cash_account_records(CASH.liabilities),
                stale_style
                + [
                    {
                        "if": {
                            "filter_query": "{balance} < 0",
                            "column_id": "balance",
                        },
                        "color": C["negative"],
                    }
                ],
            ),
        ]
    )
    deposits = _card(
        [
            _section_title("Fixed-term deposits"),
            _cash_table(
                "cash-deposits-table",
                _CASH_DEPOSIT_COLUMNS,
                _cash_deposit_records(CASH),
                _progress_bar_styles(CASH.deposits["progress_pct"])
                + [
                    {
                        "if": {"filter_query": '{status} = "Matured"'},
                        "color": C["text_muted"],
                    }
                ],
            ),
            dcc.Graph(
                id="cash-deposit-timeline",
                figure=figures.term_deposit_timeline_figure(
                    open_deposits, today
                ),
                config={"displayModeBar": False},
                style={"marginTop": "14px"},
            ),
        ]
    )
    liquidity = _card(
        [
            _section_title("Available vs. bound cash"),
            dcc.Graph(
                id="cash-liquidity",
                figure=figures.cash_liquidity_figure(CASH.liquidity),
                config={"displayModeBar": False},
            ),
        ]
    )
    return _tab_shell(
        tab["label"],
        tab["kind"],
        [_cash_kpis(CASH, today), accounts, deposits, liabilities, liquidity],
    )


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
                style={"marginTop": "8px", "maxWidth": "720px"},
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
_register_allocation_callbacks()
_register_sold_callbacks()
_register_earnings_callbacks()


def main() -> None:
    import os

    debug = os.environ.get("DASH_DEBUG", "1") not in ("0", "false", "False")
    reload = os.environ.get("DASH_RELOAD", "0") not in ("0", "false", "False")
    port = int(os.environ.get("DASH_PORT", "8050"))
    app.run(debug=debug, use_reloader=reload, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()

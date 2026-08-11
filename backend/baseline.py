"""The dashboard you see on load, expressed as blocks.

This exists so the baseline is not special. It is built from the same block
types the model chooses from and compiled by the same `a2ui` module, which
means anything on screen at load is something the agent could also have
produced -- and any bug in the compiler shows up immediately, before you type
a single request.
"""

from __future__ import annotations

from mock_data import (
    EXPENSES_BY_CATEGORY,
    KPIS,
    MONTHLY,
    REVENUE_BY_PRODUCT,
    TRANSACTIONS,
)
from schemas import (
    BarChart,
    Block,
    BlockAction,
    Column,
    DataTable,
    DonutChart,
    LineChart,
    Point,
    Series,
    Slice,
    StatCard,
)


def _money(value: float) -> str:
    """Match the client's `formatFull` so a figure looks the same everywhere."""
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def blocks() -> list[Block]:
    months = [row["month"] for row in MONTHLY]

    kpis: list[Block] = [
        StatCard(
            type="stat_card",
            title=kpi["label"],
            value=kpi["value"],
            unit=kpi["unit"],
            delta_pct=kpi["delta_pct"],
            delta_direction=kpi["delta_direction"],
            caption=kpi["caption"],
            actions=[],
        )
        for kpi in KPIS
    ]

    revenue_vs_expenses = LineChart(
        type="line_chart",
        title="Revenue vs. Expenses",
        x_label="Month",
        y_label="Amount",
        unit="USD",
        series=[
            Series(
                name="Revenue",
                points=[Point(x=m, y=r["revenue"]) for m, r in zip(months, MONTHLY)],
            ),
            Series(
                name="Expenses",
                points=[Point(x=m, y=r["expenses"]) for m, r in zip(months, MONTHLY)],
            ),
        ],
        actions=[
            BlockAction(
                label="Show net cash flow",
                prompt="Show net cash flow by month as a bar chart",
            )
        ],
    )

    cash_flow = BarChart(
        type="bar_chart",
        title="Net Cash Flow by Month",
        x_label="Month",
        y_label="Net cash flow",
        unit="USD",
        stacked=False,
        series=[
            Series(
                name="Net cash flow",
                points=[Point(x=m, y=r["cash_flow"]) for m, r in zip(months, MONTHLY)],
            )
        ],
        actions=[],
    )

    expenses = BarChart(
        type="bar_chart",
        title="Expenses by Category",
        x_label="Category",
        y_label="Amount",
        unit="USD",
        stacked=False,
        series=[
            Series(
                name="Expenses",
                points=[
                    Point(x=row["category"], y=row["amount"]) for row in EXPENSES_BY_CATEGORY
                ],
            )
        ],
        actions=[
            BlockAction(label="As a share of total", prompt="Show expenses by category as a donut")
        ],
    )

    products = DonutChart(
        type="donut_chart",
        title="Revenue by Product Line",
        unit="USD",
        slices=[
            Slice(label=row["product"], value=row["amount"]) for row in REVENUE_BY_PRODUCT
        ],
        actions=[
            BlockAction(label="Break down by region", prompt="Break down revenue by region")
        ],
    )

    transactions = DataTable(
        type="data_table",
        title="Recent Transactions",
        columns=[
            Column(key="date", label="Date", align="left"),
            Column(key="description", label="Description", align="left"),
            Column(key="category", label="Category", align="left"),
            Column(key="amount", label="Amount", align="right"),
            Column(key="status", label="Status", align="left"),
        ],
        rows=[
            [
                row["date"],
                row["description"],
                row["category"],
                _money(row["amount"]),
                row["status"],
            ]
            for row in TRANSACTIONS
        ],
        actions=[
            BlockAction(label="Largest only", prompt="List the largest transactions by amount")
        ],
    )

    return [*kpis, revenue_vs_expenses, cash_flow, expenses, products, transactions]

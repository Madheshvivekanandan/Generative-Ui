"""The one and only source of truth for the demo's financial data.

The dashboard renders from this, and the same numbers are injected into the
LLM prompt so the model fills components with data the user can actually see.
No database, no persistence -- it is a module-level constant on purpose.
"""

from __future__ import annotations

MONTHS = [
    "2025-09",
    "2025-10",
    "2025-11",
    "2025-12",
    "2026-01",
    "2026-02",
    "2026-03",
    "2026-04",
    "2026-05",
    "2026-06",
    "2026-07",
    "2026-08",
]

# All money values are USD thousands rounded to whole dollars for readability.
MONTHLY = [
    {"month": "2025-09", "revenue": 412000, "expenses": 358000, "cash_flow": 54000},
    {"month": "2025-10", "revenue": 438000, "expenses": 371000, "cash_flow": 67000},
    {"month": "2025-11", "revenue": 401000, "expenses": 383000, "cash_flow": 18000},
    {"month": "2025-12", "revenue": 496000, "expenses": 402000, "cash_flow": 94000},
    {"month": "2026-01", "revenue": 455000, "expenses": 418000, "cash_flow": 37000},
    {"month": "2026-02", "revenue": 471000, "expenses": 409000, "cash_flow": 62000},
    {"month": "2026-03", "revenue": 523000, "expenses": 431000, "cash_flow": 92000},
    {"month": "2026-04", "revenue": 508000, "expenses": 445000, "cash_flow": 63000},
    {"month": "2026-05", "revenue": 561000, "expenses": 452000, "cash_flow": 109000},
    {"month": "2026-06", "revenue": 594000, "expenses": 468000, "cash_flow": 126000},
    {"month": "2026-07", "revenue": 572000, "expenses": 481000, "cash_flow": 91000},
    {"month": "2026-08", "revenue": 631000, "expenses": 494000, "cash_flow": 137000},
]

EXPENSES_BY_CATEGORY = [
    {"category": "Payroll", "amount": 2884000},
    {"category": "Cloud & Infrastructure", "amount": 941000},
    {"category": "Marketing", "amount": 612000},
    {"category": "Software & Tools", "amount": 288000},
    {"category": "Professional Services", "amount": 197000},
    {"category": "Travel", "amount": 121000},
    {"category": "Office & Facilities", "amount": 69000},
]

REVENUE_BY_PRODUCT = [
    {"product": "Subscriptions", "amount": 3742000},
    {"product": "Professional Services", "amount": 1284000},
    {"product": "Licensing", "amount": 636000},
]

REVENUE_BY_REGION = [
    {"region": "North America", "amount": 3106000},
    {"region": "Europe", "amount": 1489000},
    {"region": "Asia Pacific", "amount": 812000},
    {"region": "Latin America", "amount": 255000},
]

TRANSACTIONS = [
    {"date": "2026-08-09", "description": "Northwind Corp - annual renewal", "category": "Subscriptions", "amount": 84000, "status": "Cleared"},
    {"date": "2026-08-08", "description": "AWS - August usage", "category": "Cloud & Infrastructure", "amount": -71400, "status": "Cleared"},
    {"date": "2026-08-07", "description": "August payroll run", "category": "Payroll", "amount": -238500, "status": "Cleared"},
    {"date": "2026-08-06", "description": "Helio Systems - implementation", "category": "Professional Services", "amount": 46500, "status": "Cleared"},
    {"date": "2026-08-05", "description": "LinkedIn Ads", "category": "Marketing", "amount": -18900, "status": "Cleared"},
    {"date": "2026-08-04", "description": "Braxton Retail - platform license", "category": "Licensing", "amount": 52000, "status": "Pending"},
    {"date": "2026-08-03", "description": "Datadog - annual plan", "category": "Software & Tools", "amount": -24000, "status": "Cleared"},
    {"date": "2026-08-01", "description": "Vertex Labs - monthly subscription", "category": "Subscriptions", "amount": 31000, "status": "Cleared"},
    {"date": "2026-07-29", "description": "Office lease - Q3", "category": "Office & Facilities", "amount": -17250, "status": "Cleared"},
    {"date": "2026-07-27", "description": "Meridian Bank - enterprise tier", "category": "Subscriptions", "amount": 96000, "status": "Cleared"},
    {"date": "2026-07-24", "description": "Conference travel - SaaSConf", "category": "Travel", "amount": -12800, "status": "Cleared"},
    {"date": "2026-07-22", "description": "Outside counsel - contract review", "category": "Professional Services", "amount": -9400, "status": "Overdue"},
    {"date": "2026-07-20", "description": "Cobalt Group - services retainer", "category": "Professional Services", "amount": 38000, "status": "Cleared"},
    {"date": "2026-07-18", "description": "Google Cloud - July usage", "category": "Cloud & Infrastructure", "amount": -29600, "status": "Cleared"},
    {"date": "2026-07-15", "description": "Ardent Health - annual renewal", "category": "Subscriptions", "amount": 128000, "status": "Cleared"},
]

KPIS = [
    {"label": "Revenue (TTM)", "value": 6062000, "unit": "USD", "delta_pct": 18.4, "delta_direction": "up", "caption": "vs. prior 12 months"},
    {"label": "Expenses (TTM)", "value": 5112000, "unit": "USD", "delta_pct": 11.2, "delta_direction": "up", "caption": "vs. prior 12 months"},
    {"label": "Net Cash Flow (TTM)", "value": 950000, "unit": "USD", "delta_pct": 46.1, "delta_direction": "up", "caption": "vs. prior 12 months"},
    {"label": "Gross Margin", "value": 68.4, "unit": "%", "delta_pct": 2.1, "delta_direction": "up", "caption": "trailing 12 months"},
]


def dashboard_payload() -> dict:
    """The full mock dataset, as served to the frontend on load."""
    return {
        "currency": "USD",
        "period": {"start": MONTHS[0], "end": MONTHS[-1]},
        "kpis": KPIS,
        "monthly": MONTHLY,
        "expenses_by_category": EXPENSES_BY_CATEGORY,
        "revenue_by_product": REVENUE_BY_PRODUCT,
        "revenue_by_region": REVENUE_BY_REGION,
        "transactions": TRANSACTIONS,
    }


def dataset_for_prompt() -> str:
    """A compact, readable rendering of the dataset for the system prompt.

    Plain text beats raw JSON here: it is a third of the tokens and the model
    copies numbers out of it more reliably.
    """
    lines: list[str] = []
    lines.append(f"Reporting period: {MONTHS[0]} through {MONTHS[-1]}. All amounts in USD.")

    lines.append("")
    lines.append("MONTHLY TOTALS (month | revenue | expenses | net cash flow):")
    for row in MONTHLY:
        lines.append(
            f"  {row['month']} | {row['revenue']} | {row['expenses']} | {row['cash_flow']}"
        )

    lines.append("")
    lines.append("EXPENSES BY CATEGORY, full period (category | amount):")
    for row in EXPENSES_BY_CATEGORY:
        lines.append(f"  {row['category']} | {row['amount']}")

    lines.append("")
    lines.append("REVENUE BY PRODUCT LINE, full period (product | amount):")
    for row in REVENUE_BY_PRODUCT:
        lines.append(f"  {row['product']} | {row['amount']}")

    lines.append("")
    lines.append("REVENUE BY REGION, full period (region | amount):")
    for row in REVENUE_BY_REGION:
        lines.append(f"  {row['region']} | {row['amount']}")

    lines.append("")
    lines.append("HEADLINE KPIS (label | value | unit | change % vs prior period):")
    for row in KPIS:
        lines.append(f"  {row['label']} | {row['value']} | {row['unit']} | {row['delta_pct']}")

    lines.append("")
    lines.append("RECENT TRANSACTIONS (date | description | category | amount | status).")
    lines.append("Negative amounts are money out, positive are money in:")
    for row in TRANSACTIONS:
        lines.append(
            f"  {row['date']} | {row['description']} | {row['category']} "
            f"| {row['amount']} | {row['status']}"
        )

    return "\n".join(lines)

from __future__ import annotations

from pydantic import BaseModel

from schemas.category_amount import CategoryAmount
from schemas.kpi import Kpi
from schemas.monthly_row import MonthlyRow
from schemas.period import Period
from schemas.product_amount import ProductAmount
from schemas.region_amount import RegionAmount
from schemas.transaction import Transaction


class DashboardResponse(BaseModel):
    """The mock dataset. Typed so OpenAPI documents it and the fixtures are validated."""

    currency: str
    period: Period
    kpis: list[Kpi]
    monthly: list[MonthlyRow]
    expenses_by_category: list[CategoryAmount]
    revenue_by_product: list[ProductAmount]
    revenue_by_region: list[RegionAmount]
    transactions: list[Transaction]

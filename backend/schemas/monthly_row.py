from __future__ import annotations

from pydantic import BaseModel


class MonthlyRow(BaseModel):
    month: str
    revenue: float
    expenses: float
    cash_flow: float

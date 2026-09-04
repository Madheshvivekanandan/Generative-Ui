from __future__ import annotations

from pydantic import BaseModel


class ProductAmount(BaseModel):
    product: str
    amount: float

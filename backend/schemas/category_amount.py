from __future__ import annotations

from pydantic import BaseModel


class CategoryAmount(BaseModel):
    category: str
    amount: float

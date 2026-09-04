from __future__ import annotations

from pydantic import BaseModel


class Transaction(BaseModel):
    date: str
    description: str
    category: str
    amount: float
    status: str

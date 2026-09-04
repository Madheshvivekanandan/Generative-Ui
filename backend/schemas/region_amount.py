from __future__ import annotations

from pydantic import BaseModel


class RegionAmount(BaseModel):
    region: str
    amount: float

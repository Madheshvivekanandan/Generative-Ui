from __future__ import annotations

from pydantic import BaseModel

from schemas.types import Direction, Unit


class Kpi(BaseModel):
    label: str
    value: float
    unit: Unit
    delta_pct: float
    delta_direction: Direction
    caption: str

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from schemas.block_action import BlockAction
from schemas.slice import Slice
from schemas.types import Unit


class DonutChart(BaseModel):
    """Composition of a whole. Only when parts genuinely sum to 100%."""

    type: Literal["donut_chart"]
    title: str
    unit: Unit
    slices: list[Slice] = Field(
        description="Two to six slices, largest first. Roll up the tail into 'Other'."
    )
    actions: list[BlockAction] = Field(description="Zero to two follow-on actions.")

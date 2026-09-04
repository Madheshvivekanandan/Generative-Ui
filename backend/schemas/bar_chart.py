from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from schemas.block_action import BlockAction
from schemas.series import Series
from schemas.types import Unit


class BarChart(BaseModel):
    """Comparison across categories, or period-over-period totals."""

    type: Literal["bar_chart"]
    title: str
    x_label: str
    y_label: str
    unit: Unit
    stacked: bool = Field(description="True only when the series sum to a meaningful total.")
    series: list[Series] = Field(description="One to four series sharing the same x values.")
    actions: list[BlockAction] = Field(description="Zero to two follow-on actions.")

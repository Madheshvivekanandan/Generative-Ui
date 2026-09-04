from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from schemas.block_action import BlockAction
from schemas.series import Series
from schemas.types import Unit


class LineChart(BaseModel):
    """Change over time. Use for anything trending across months."""

    type: Literal["line_chart"]
    title: str
    x_label: str
    y_label: str
    unit: Unit
    series: list[Series] = Field(description="One to four series. More than four is unreadable.")
    actions: list[BlockAction] = Field(description="Zero to two follow-on actions.")

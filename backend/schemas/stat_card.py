from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from schemas.block_action import BlockAction
from schemas.types import Direction, Unit


class StatCard(BaseModel):
    """A single headline number. Use when the answer is one figure."""

    type: Literal["stat_card"]
    # `title` names the measure -- "Net Cash Flow (Q4)". There is deliberately
    # no separate label field: the title is the heading, and a second copy of
    # the same words underneath it is what the previous version rendered.
    title: str
    value: float
    unit: Unit
    delta_pct: float = Field(description="Percent change vs. the comparison period; 0 if unknown.")
    delta_direction: Direction
    caption: str = Field(description="Short context line, e.g. 'vs. prior 12 months'.")
    actions: list[BlockAction] = Field(description="Zero to two follow-on actions.")

"""The block union: everything the model may put in a turn.

Deliberately a bare union, NOT a `Field(discriminator=...)` -- Pydantic renders
a discriminator as the JSON-Schema `discriminator` keyword, which OpenAI's
strict structured-outputs mode rejects. The `Literal` type tag on each member
does the discriminating.
"""

from __future__ import annotations

from schemas.bar_chart import BarChart
from schemas.data_table import DataTable
from schemas.donut_chart import DonutChart
from schemas.line_chart import LineChart
from schemas.stat_card import StatCard
from schemas.text_note import TextNote

Block = StatCard | LineChart | BarChart | DonutChart | DataTable | TextNote

BLOCK_TYPES = ("stat_card", "line_chart", "bar_chart", "donut_chart", "data_table", "text_note")

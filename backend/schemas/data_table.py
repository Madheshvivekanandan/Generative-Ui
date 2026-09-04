from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from schemas.block_action import BlockAction
from schemas.column import Column


class DataTable(BaseModel):
    """Raw records. Use when the user asks to list, show or filter rows."""

    type: Literal["data_table"]
    title: str
    columns: list[Column]
    rows: list[list[str]] = Field(
        description="Each row has exactly one pre-formatted string per column, in column order."
    )
    actions: list[BlockAction] = Field(description="Zero to two follow-on actions.")

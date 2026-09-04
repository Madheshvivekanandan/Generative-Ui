from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from schemas.block_action import BlockAction


class TextNote(BaseModel):
    """A written answer. Use when no chart fits, or the request is out of scope."""

    type: Literal["text_note"]
    title: str
    body: str = Field(description="Two or three sentences at most.")
    actions: list[BlockAction] = Field(description="Zero to two follow-on actions.")

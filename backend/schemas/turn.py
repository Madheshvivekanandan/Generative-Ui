from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Turn(BaseModel):
    """One exchange, replayed to the model so follow-ups can say 'that'."""

    role: Literal["user", "assistant"]
    content: str

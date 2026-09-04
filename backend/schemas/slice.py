from __future__ import annotations

from pydantic import BaseModel, Field


class Slice(BaseModel):
    label: str
    value: float = Field(description="Must be non-negative; shares of a whole.")

from __future__ import annotations

from pydantic import BaseModel, Field


class Point(BaseModel):
    """One (category or time bucket, value) pair."""

    x: str = Field(description="Axis label, e.g. '2026-03' or 'Marketing'.")
    y: float = Field(description="The numeric value at x.")

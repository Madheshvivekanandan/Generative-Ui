from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.point import Point


class Series(BaseModel):
    name: str = Field(description="Series name shown in the legend, e.g. 'Revenue'.")
    points: list[Point] = Field(description="Points in display order, left to right.")

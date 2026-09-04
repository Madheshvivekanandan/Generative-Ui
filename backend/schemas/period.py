from __future__ import annotations

from pydantic import BaseModel


class Period(BaseModel):
    start: str
    end: str

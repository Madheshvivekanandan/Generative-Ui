from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model: str
    openai_key_set: bool
    protocol: str
    catalog_id: str

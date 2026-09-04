from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.types import Align


class Column(BaseModel):
    key: str = Field(description="Short identifier, e.g. 'amount'.")
    label: str = Field(description="Human-readable header, e.g. 'Amount (USD)'.")
    align: Align = Field(description="Use 'right' for numeric columns, 'left' otherwise.")

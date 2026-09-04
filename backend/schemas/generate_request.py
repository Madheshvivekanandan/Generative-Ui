from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GenerateRequest(BaseModel):
    # Reject unknown keys outright rather than ignoring them, so a client
    # sending the wrong shape finds out immediately.
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(min_length=1, max_length=128)

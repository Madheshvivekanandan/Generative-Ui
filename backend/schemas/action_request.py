from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ActionRequest(BaseModel):
    """An A2UI action message relayed by the client.

    The renderer posts the action it received from the user; the agent treats
    the carried prompt as the next user turn. This is the client-to-server half
    of the A2UI loop.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=64)
    surface_id: str = Field(default="", max_length=128)
    context: dict[str, str] = Field(default_factory=dict)

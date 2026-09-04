"""The one shape everything downstream of the agent consumes."""

from __future__ import annotations

from typing import Literal, NamedTuple


class Event(NamedTuple):
    """One thing to push down the SSE connection."""

    kind: Literal["a2ui", "meta"]
    payload: dict

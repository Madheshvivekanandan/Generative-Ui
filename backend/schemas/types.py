"""Shared literal types used across the block catalog and the read models."""

from __future__ import annotations

from typing import Literal

Unit = Literal["USD", "%", "count", "none"]
Direction = Literal["up", "down", "flat"]
Align = Literal["left", "right"]

# A stable code per failure mode, never an exception message. The browser gets
# this plus generic prose; anything more specific would leak internals.
ErrorCode = Literal[
    "missing_api_key",
    "schema_validation_failed",
    "unusable_blocks",
    "upstream_error",
]

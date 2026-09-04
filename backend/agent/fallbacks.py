"""Every user-facing failure, in one place.

The copy is deliberately generic: an upstream exception message can carry a
partial API key or other internals, and whatever goes in `body` is rendered
verbatim in the browser. Diagnostics belong in the log.
"""

from __future__ import annotations

from typing import Iterator

import a2ui
from agent.config import DEFAULT_FOLLOW_UPS
from agent.emit import emit_blocks
from agent.events import Event
from schemas import ErrorCode

FALLBACK_COPY: dict[ErrorCode, tuple[str, str]] = {
    "missing_api_key": (
        "Missing API key",
        "Set OPENAI_API_KEY in the server's environment and restart it, then try again. "
        "Locally that is backend/.env; under Docker it is the .env next to compose.yaml.",
    ),
    "schema_validation_failed": (
        "Could not render that",
        "The model returned something outside the component catalog. "
        "Try rephrasing, for example: 'show revenue by month as a line chart'.",
    ),
    "unusable_blocks": (
        "Could not render that",
        "Nothing renderable came back. Try rephrasing your request.",
    ),
    "upstream_error": (
        "Something went wrong",
        "The dashboard couldn't reach the model. Check the server logs and try again.",
    ),
}


def fallback(surface_id: str, error: ErrorCode) -> Iterator[Event]:
    """A renderable stand-in, so no failure leaves the surface empty."""
    title, body = FALLBACK_COPY[error]
    yield from emit_blocks(surface_id, [a2ui.text_note(title, body)])
    yield Event(
        "meta",
        {
            "ok": False,
            "explanation": body,
            "follow_ups": DEFAULT_FOLLOW_UPS,
            "fallback": True,
            "error": error,
        },
    )

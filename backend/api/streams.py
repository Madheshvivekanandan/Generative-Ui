"""SSE framing and the per-turn stream shared by /api/generate and /api/action."""

from __future__ import annotations

import json
import logging
from typing import Iterator

import agent
from fastapi.responses import StreamingResponse
from session import store

logger = logging.getLogger("genui.api")

# The one surface everything renders into -- the baseline at load, and every
# generated turn after it. A fixed id is what makes the dashboard re-compose in
# place: the client deletes it, the next createSurface re-opens the same id at
# the same position, and replace-wins semantics do the rest. (v0.9.1 explicitly
# allows reusing the id of a deleted surface.)
CANVAS_SURFACE = "dashboard"


def sse_frame(event: agent.Event) -> str:
    """One A2UI message (or one chat-metadata object) as an SSE frame.

    A2UI's own MIME type is `application/a2ui+json` over a JSONL stream; SSE
    carries the same JSON objects one per frame, which is what the browser can
    consume without a custom transport. The `event:` name tells the client
    which of the two channels a frame belongs to.
    """
    return f"event: {event.kind}\ndata: {json.dumps(event.payload)}\n\n"


def turn_stream(session_id: str, message: str) -> Iterator[str]:
    """Run one turn into the canvas surface, recording the transcript.

    The surface id is always the canvas: the client clears it with a
    `deleteSurface` before this stream's `createSurface` re-opens it, which is
    what makes the new answer form at the same place, same position.
    """
    history = store.history(session_id)
    surface_id = CANVAS_SURFACE

    # Announced first so any client (curl included) knows which surface the
    # turn is about to re-compose before the first A2UI frame lands.
    yield f"event: open\ndata: {json.dumps({'surface_id': surface_id})}\n\n"

    summary = ""
    try:
        for event in agent.run(message, history, surface_id):
            if event.kind == "meta":
                rendered = event.payload.get("rendered") or []
                summary = event.payload.get("explanation", "")
                if rendered:
                    summary = f"{summary} [rendered: {', '.join(rendered)}]"
            yield sse_frame(event)
    finally:
        # Recorded even on a fallback: the user asked, and the next turn should
        # know they asked, whatever came back.
        store.record(session_id, message, summary or "(nothing rendered)")

    yield "event: done\ndata: {}\n\n"


def stream_response(session_id: str, message: str) -> StreamingResponse:
    return StreamingResponse(
        turn_stream(session_id, message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # nginx buffers proxied responses by default, which would hold the
            # whole stream until the turn finished and defeat the point.
            "X-Accel-Buffering": "no",
        },
    )

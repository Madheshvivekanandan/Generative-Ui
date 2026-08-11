"""Generative UI backend, speaking A2UI v0.9.

POST a free-text message and the response is a stream of A2UI messages that
`@a2ui/react` renders directly -- `createSurface`, then `updateDataModel` and
`updateComponents` as the agent composes the answer. Buttons the agent puts on
those cards post back to `/api/action`, which is the client-to-server half of
the loop and re-enters the same generator with the conversation intact.

The stream never raises to the client: a missing API key, an OpenAI error or a
schema violation all resolve to a `text_note` block, so the renderer is never
handed a surface it cannot draw.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Iterator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import a2ui
import agent
import baseline
from mock_data import dashboard_payload
from schemas import (
    ActionRequest,
    DashboardResponse,
    GenerateRequest,
    HealthResponse,
)
from session import store

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("genui")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

# The baseline dashboard's surface. Fixed, so a reload replaces it rather than
# stacking a second copy alongside the first.
BASELINE_SURFACE = "dashboard"

app = FastAPI(title="Generative UI — A2UI Financial Dashboard", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _sse(event: agent.Event) -> str:
    """One A2UI message (or one chat-metadata object) as an SSE frame.

    A2UI's own MIME type is `application/a2ui+json` over a JSONL stream; SSE
    carries the same JSON objects one per frame, which is what the browser can
    consume without a custom transport. The `event:` name tells the client
    which of the two channels a frame belongs to.
    """
    return f"event: {event.kind}\ndata: {json.dumps(event.payload)}\n\n"


def _turn_stream(session_id: str, message: str) -> Iterator[str]:
    """Run one turn, forwarding every message and recording the transcript."""
    history = store.history(session_id)
    surface_id = f"turn-{uuid.uuid4().hex[:12]}"

    # The client needs the surface id before anything else so it can slot the
    # card into the layout the moment createSurface lands.
    yield f"event: open\ndata: {json.dumps({'surface_id': surface_id})}\n\n"

    summary = ""
    try:
        for event in agent.run(message, history, surface_id):
            if event.kind == "meta":
                rendered = event.payload.get("rendered") or []
                summary = event.payload.get("explanation", "")
                if rendered:
                    summary = f"{summary} [rendered: {', '.join(rendered)}]"
            yield _sse(event)
    finally:
        # Recorded even on a fallback: the user asked, and the next turn should
        # know they asked, whatever came back.
        store.record(session_id, message, summary or "(nothing rendered)")

    yield "event: done\ndata: {}\n\n"


def _stream_response(session_id: str, message: str) -> StreamingResponse:
    return StreamingResponse(
        _turn_stream(session_id, message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # nginx buffers proxied responses by default, which would hold the
            # whole stream until the turn finished and defeat the point.
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health", response_model=HealthResponse, summary="Liveness and configuration")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=agent.MODEL,
        openai_key_set=bool(os.getenv("OPENAI_API_KEY")),
        protocol=a2ui.VERSION,
        catalog_id=a2ui.CATALOG_ID,
    )


@app.get("/api/dashboard", response_model=DashboardResponse, summary="The mock dataset")
def dashboard() -> DashboardResponse:
    """The raw mock dataset. Kept for `curl` and `/docs`; the UI uses the A2UI form."""
    return DashboardResponse.model_validate(dashboard_payload())


@app.get("/api/dashboard/a2ui", summary="The baseline dashboard as A2UI messages")
def dashboard_a2ui() -> dict:
    """The load-time dashboard, compiled by the same path a generated turn takes.

    It arrives in one `createSurface` rather than a stream because none of it
    is being composed live -- but the components and bindings are identical to
    what the agent emits, which is the point.
    """
    return {
        "surface_id": BASELINE_SURFACE,
        "messages": a2ui.full_surface(BASELINE_SURFACE, baseline.blocks()),
    }


@app.post("/api/generate", summary="Stream A2UI messages for one request")
def generate(request: GenerateRequest) -> StreamingResponse:
    """Turn a free-text request into a stream of A2UI v0.9 messages."""
    return _stream_response(request.session_id, request.message)


@app.post("/api/action", summary="Handle an A2UI action from the renderer")
def action(request: ActionRequest) -> StreamingResponse:
    """The client-to-server half of A2UI: a user pressed a generated button.

    The agent attached the request it wants back as the action's `prompt`
    context, so handling any action is just re-entering the generator with
    that text. One handler covers every button the model can invent.
    """
    if request.name != a2ui.REFINE_ACTION:
        logger.warning("ignoring unknown action: %s", request.name)

    prompt = (request.context.get("prompt") or "").strip()
    if not prompt:
        # Nothing actionable arrived; say so through the same stream shape
        # rather than inventing an error the client would have to special-case.
        prompt = "Explain what this dashboard can show me."

    return _stream_response(request.session_id, prompt)

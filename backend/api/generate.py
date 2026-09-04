from __future__ import annotations

import logging

import a2ui
from api.streams import stream_response
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from schemas import ActionRequest, GenerateRequest

logger = logging.getLogger("genui.api")

router = APIRouter()


@router.post("/api/generate", summary="Stream A2UI messages for one request")
def generate(request: GenerateRequest) -> StreamingResponse:
    """Turn a free-text request into a stream of A2UI v0.9 messages."""
    return stream_response(request.session_id, request.message)


@router.post("/api/action", summary="Handle an A2UI action from the renderer")
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

    return stream_response(request.session_id, prompt)

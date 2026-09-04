"""The streaming loop: free-text in, a stream of A2UI v0.9 events out.

Generation is streamed twice over, deliberately:

* **Optimistically**, from the model's partially-parsed JSON. As soon as one
  block is provably finished, its data and components are emitted, so the
  first card appears while the model is still writing the third. This is what
  makes the interface build in front of the user instead of arriving whole.
* **Authoritatively**, once the stream closes. The completed object is
  validated and sanitised, then the full data model and component tree are
  re-sent. `updateDataModel` replaces, so a block that the optimistic pass got
  wrong (or skipped) is corrected before the user can act on it.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Generator, Iterator

from pydantic import TypeAdapter, ValidationError

import a2ui
from agent.config import MODEL, get_client
from agent.emit import emit_blocks, emit_one_block
from agent.events import Event
from agent.fallbacks import fallback
from agent.follow_ups import clean_follow_ups
from agent.prompts import SYSTEM_PROMPT
from schemas import AgentTurn, Block, Turn

logger = logging.getLogger("genui.agent")

_block_adapter: TypeAdapter[Block] = TypeAdapter(Block)


def _messages(message: str, history: list[Turn]) -> list[dict]:
    replayed = [{"role": turn.role, "content": turn.content} for turn in history]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *replayed,
        {"role": "user", "content": message},
    ]


def _parse_partial_block(raw: Any) -> Block | None:
    """Validate one block out of a partially-streamed object.

    `raw` is `Any` because it comes from the SDK's partial-parse snapshot: at
    this point in the stream it may be a half-built dict, a scalar, or absent
    entirely, and narrowing it is exactly this function's job.

    Returns:
        The sanitised block, or None if it is not yet whole -- in which case the
        authoritative pass emits it properly a moment later.
    """
    if not isinstance(raw, dict) or not raw.get("type"):
        return None
    candidate = dict(raw)
    candidate.setdefault("actions", [])
    try:
        return a2ui.sanitize(_block_adapter.validate_python(candidate))
    except (ValidationError, ValueError):
        return None


def _generate(
    message: str, history: list[Turn], surface_id: str
) -> Generator[Event, None, AgentTurn]:
    """Stream the model, emitting blocks optimistically; return the whole turn.

    Args:
        message: The user's request for this turn.
        history: Prior turns, replayed so pronouns resolve.
        surface_id: The surface these blocks belong to.

    Returns:
        The completed, validated turn, for the caller's authoritative pass.

    Raises:
        ValueError: If the model refused, or returned nothing parseable.
    """
    emitted = 0
    blocks: list[Block] = []

    with get_client().beta.chat.completions.stream(
        model=MODEL,
        messages=_messages(message, history),
        response_format=AgentTurn,
        temperature=0.2,
    ) as stream:
        for event in stream:
            if event.type != "content.delta" or not event.parsed:
                continue

            raw_blocks = event.parsed.get("blocks")
            if not isinstance(raw_blocks, list):
                continue

            # A block is only provably finished once the next one has started,
            # so the last one in the snapshot is always left to the caller.
            for index in range(emitted, len(raw_blocks) - 1):
                block = _parse_partial_block(raw_blocks[index])
                if block is None:
                    break
                blocks.append(block)
                emitted = index + 1
                yield from emit_one_block(surface_id, blocks, index)

        completion = stream.get_final_completion()

    choice = completion.choices[0]
    if choice.message.refusal:
        raise ValueError(f"model refused: {choice.message.refusal}")
    if choice.message.parsed is None:
        raise ValueError("model returned no parseable output")
    return choice.message.parsed


def _usable_blocks(blocks: list[Block]) -> list[Block]:
    """Sanitise a turn's blocks, dropping any that cannot be drawn.

    One unusable block does not sink the turn -- a bad donut alongside a good
    chart should cost the donut, not the answer.
    """
    usable: list[Block] = []
    for block in blocks[: a2ui.MAX_BLOCKS]:
        try:
            usable.append(a2ui.sanitize(block))
        except ValueError as exc:
            logger.warning("dropping unusable block: %s", exc)
    return usable


def run(message: str, history: list[Turn], surface_id: str) -> Iterator[Event]:
    """Stream one turn. Never raises: every failure path yields a text_note."""
    yield Event("a2ui", a2ui.create_surface(surface_id))
    yield Event("a2ui", a2ui.update_data_model(surface_id, "/", {"blocks": []}))

    if not os.getenv("OPENAI_API_KEY"):
        yield from fallback(surface_id, "missing_api_key")
        return

    try:
        turn = yield from _generate(message, history, surface_id)
    except ValidationError as exc:
        logger.warning("model output failed validation: %s", exc)
        yield from fallback(surface_id, "schema_validation_failed")
        return
    except Exception:  # network, auth, rate limit, refusal, anything upstream
        logger.exception("generation failed")
        yield from fallback(surface_id, "upstream_error")
        return

    final = _usable_blocks(turn.blocks)
    if not final:
        yield from fallback(surface_id, "unusable_blocks")
        return

    yield from emit_blocks(surface_id, final)
    yield Event(
        "meta",
        {
            "ok": True,
            "explanation": turn.explanation,
            "follow_ups": clean_follow_ups(turn.follow_ups, message),
            "fallback": False,
            "error": None,
            # What went on screen, for the transcript. The next turn needs this
            # to resolve "that chart" without replaying the whole data model.
            "rendered": [f"{block.title} ({block.type})" for block in final],
        },
    )

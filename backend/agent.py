"""The agent: free-text in, a stream of A2UI v0.9 messages out.

Generation is streamed twice over, deliberately:

* **Optimistically**, from the model's partially-parsed JSON. As soon as one
  block is provably finished, its data and components are emitted, so the
  first card appears while the model is still writing the third. This is what
  makes the interface build in front of the user instead of arriving whole.
* **Authoritatively**, once the stream closes. The completed object is
  validated and sanitised, then the full data model and component tree are
  re-sent. `updateDataModel` replaces, so a block that the optimistic pass got
  wrong (or skipped) is corrected before the user can act on it.

Everything yielded here is either a real A2UI message (`kind="a2ui"`) or chat
metadata for the app's own log (`kind="meta"`), which is not part of A2UI.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Generator, Iterator, Literal, NamedTuple

from openai import OpenAI
from pydantic import TypeAdapter, ValidationError

import a2ui
from mock_data import dataset_for_prompt
from schemas import AgentTurn, Block, ErrorCode, Turn

logger = logging.getLogger("genui.agent")

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

MAX_FOLLOW_UPS = 3
MAX_FOLLOW_UP_CHARS = 70

DEFAULT_FOLLOW_UPS = [
    "Show revenue as a line chart",
    "Expenses by category as a bar chart",
    "What was net cash flow in August?",
]

_block_adapter: TypeAdapter[Block] = TypeAdapter(Block)

SYSTEM_PROMPT = f"""You are the rendering engine for a financial dashboard. The user \
describes what they want to see; you compose a small layout of one to \
{a2ui.MAX_BLOCKS} blocks from the catalog and fill them with real numbers from the \
dataset below.

Rules:
- Use only numbers that appear in the dataset, or arithmetic derived from them \
(sums, differences, percentages, averages). Never invent figures.
- Pick the blocks that fit the question, not the ones the user names, unless they \
name one explicitly. Trends over months are line charts. Comparisons across categories \
are bar charts. A single figure is a stat card. Composition of a whole is a donut, and \
only when the parts really do sum to that whole. Lists of records are tables.
- Prefer ONE block. Use several only when the question genuinely needs them -- a \
summary request like "how did Q3 go" earns a stat card or two above a chart; "show \
revenue by month" does not.
- Stat cards placed next to each other are laid out as a row, so a set of related \
KPIs should be consecutive blocks.
- At most {a2ui.MAX_SERIES} series per chart and at most {a2ui.MAX_SLICES} donut \
slices; roll the tail into "Other".
- Sort categorical data largest first. Keep time series in chronological order.
- Table cells are pre-formatted strings: thousands separators, a leading "$" on money, \
a leading "-" for money out.
- When asked for the largest, smallest, top or biggest records, sort by the relevant \
measure across the WHOLE dataset before selecting, and return every row that qualifies \
(up to {a2ui.MAX_ROWS}). Do not stop at the first few rows you happen to read.
- If the request is unrelated to this data or cannot be answered from it, return a \
single text_note saying so plainly. Do not guess.
- Every block needs a short, specific title -- "Revenue by Month", not "A chart of \
the revenue" and never the literal word "Title". This applies to text_note too: title \
it with the subject, e.g. "Out of scope".
- Each block may carry up to {a2ui.MAX_ACTIONS} actions. These become buttons ON the \
card. Use them for the obvious next move from THAT block -- "Split by region", "Show \
as a table", "Compare to expenses". The prompt you attach is sent back to you verbatim \
when the button is clicked, so write it as a complete, self-contained request. Give a \
block no actions when nothing obvious follows from it.
- Always return exactly three follow_ups: short requests the user could send next, \
phrased the way they would type them ("Compare against expenses", not "Would you like \
to compare against expenses?"). Each must be answerable from this dataset, must lead \
somewhere different from the other two, and must not restate the request you just \
answered. Under 60 characters each. If the request was out of scope, suggest three \
things this dashboard CAN answer.
- The conversation so far is replayed to you. Resolve "that", "it" and "the previous \
chart" against it rather than asking what the user meant.

DATASET
{dataset_for_prompt()}
"""


class Event(NamedTuple):
    """One thing to push down the SSE connection."""

    kind: Literal["a2ui", "meta"]
    payload: dict


_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Lazily build the OpenAI client so the app still boots without a key."""
    global _client
    if _client is None:
        _client = OpenAI()  # reads OPENAI_API_KEY from the environment
    return _client


def clean_follow_ups(raw: list[str], asked: str) -> list[str]:
    """Trim, de-duplicate and drop anything that just echoes the request.

    Unlike a block, a bad follow-up is not worth failing the turn over -- an
    empty list simply renders no chips.
    """
    seen: set[str] = {asked.strip().casefold()}
    cleaned: list[str] = []

    for item in raw:
        text = " ".join(item.split())
        key = text.casefold()
        if not text or len(text) > MAX_FOLLOW_UP_CHARS or key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) == MAX_FOLLOW_UPS:
            break

    return cleaned


def _messages(message: str, history: list[Turn]) -> list[dict]:
    replayed = [{"role": turn.role, "content": turn.content} for turn in history]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *replayed,
        {"role": "user", "content": message},
    ]


def _emit_blocks(surface_id: str, blocks: list[Block]) -> Iterator[Event]:
    """Data model, components and root for a full set of blocks."""
    yield Event("a2ui", a2ui.update_data_model(surface_id, "/", a2ui.data_model(blocks)))
    yield Event("a2ui", a2ui.update_components(surface_id, a2ui.component_tree(blocks)))


def _emit_one_block(surface_id: str, blocks: list[Block], index: int) -> Iterator[Event]:
    """Append a single freshly-completed block, keeping the root in step.

    Only this block's data is written, but the whole tree is resent: grouping
    consecutive stat cards into a Row means an earlier block's parent can
    change when a later one arrives.
    """
    yield Event(
        "a2ui",
        a2ui.update_data_model(surface_id, f"/blocks/{index}", a2ui.block_data(blocks[index])),
    )
    yield Event("a2ui", a2ui.update_components(surface_id, a2ui.component_tree(blocks)))


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
                yield from _emit_one_block(surface_id, blocks, index)

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


# Every user-facing failure, in one place. The copy is deliberately generic:
# an upstream exception message can carry a partial API key or other internals,
# and whatever goes in `body` is rendered verbatim in the browser. Diagnostics
# belong in the log.
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


def _fallback(surface_id: str, error: ErrorCode) -> Iterator[Event]:
    """A renderable stand-in, so no failure leaves the surface empty."""
    title, body = FALLBACK_COPY[error]
    yield from _emit_blocks(surface_id, [a2ui.text_note(title, body)])
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


def run(message: str, history: list[Turn], surface_id: str) -> Iterator[Event]:
    """Stream one turn. Never raises: every failure path yields a text_note."""
    yield Event("a2ui", a2ui.create_surface(surface_id))
    yield Event("a2ui", a2ui.update_data_model(surface_id, "/", {"blocks": []}))

    if not os.getenv("OPENAI_API_KEY"):
        yield from _fallback(surface_id, "missing_api_key")
        return

    try:
        turn = yield from _generate(message, history, surface_id)
    except ValidationError as exc:
        logger.warning("model output failed validation: %s", exc)
        yield from _fallback(surface_id, "schema_validation_failed")
        return
    except Exception:  # network, auth, rate limit, refusal, anything upstream
        logger.exception("generation failed")
        yield from _fallback(surface_id, "upstream_error")
        return

    final = _usable_blocks(turn.blocks)
    if not final:
        yield from _fallback(surface_id, "unusable_blocks")
        return

    yield from _emit_blocks(surface_id, final)
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

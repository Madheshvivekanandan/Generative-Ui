"""Turning blocks into the A2UI events a stream yields."""

from __future__ import annotations

from typing import Iterator

import a2ui
from agent.events import Event
from schemas import Block


def emit_blocks(surface_id: str, blocks: list[Block]) -> Iterator[Event]:
    """Data model, components and root for a full set of blocks."""
    yield Event("a2ui", a2ui.update_data_model(surface_id, "/", a2ui.data_model(blocks)))
    yield Event("a2ui", a2ui.update_components(surface_id, a2ui.component_tree(blocks)))


def emit_one_block(surface_id: str, blocks: list[Block], index: int) -> Iterator[Event]:
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

"""Content limits the schema cannot express: shape is not sense."""

from __future__ import annotations

from a2ui.constants import MAX_ACTIONS, MAX_POINTS, MAX_ROWS, MAX_SERIES, MAX_SLICES
from schemas import BarChart, Block, DataTable, DonutChart, LineChart, TextNote


def sanitize(block: Block) -> Block:
    """Enforce the limits the prompt asks for but the schema cannot express.

    Structured outputs guarantee the shape, not the sense of it -- a model can
    still return nine series or a table row with the wrong number of cells. We
    trim what is trimmable and raise on what is not, so the caller can drop
    this block and keep the rest of the turn.
    """
    block.actions = block.actions[:MAX_ACTIONS]

    if isinstance(block, (LineChart, BarChart)):
        block.series = block.series[:MAX_SERIES]
        if not block.series:
            raise ValueError("chart has no series")
        for series in block.series:
            series.points = series.points[:MAX_POINTS]
        if not any(series.points for series in block.series):
            raise ValueError("chart has no data points")

    elif isinstance(block, DonutChart):
        slices = [s for s in block.slices if s.value > 0][:MAX_SLICES]
        if len(slices) < 2:
            raise ValueError("donut needs at least two positive slices")
        block.slices = slices

    elif isinstance(block, DataTable):
        if not block.columns:
            raise ValueError("table has no columns")
        width = len(block.columns)
        # Drop malformed rows rather than shipping a ragged table.
        block.rows = [row for row in block.rows[:MAX_ROWS] if len(row) == width]
        if not block.rows:
            raise ValueError("table has no well-formed rows")

    return block


def text_note(title: str, body: str) -> TextNote:
    return TextNote(type="text_note", title=title, body=body, actions=[])

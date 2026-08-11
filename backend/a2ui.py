"""A2UI v0.9 wire format: message builders and the block -> A2UI compiler.

The agent plans in the typed blocks from `schemas.py`; everything the browser
actually receives is emitted here as genuine A2UI v0.9 messages
(`createSurface`, `updateComponents`, `updateDataModel`, `deleteSurface`),
which `@a2ui/react` renders directly. Nothing downstream of this module knows
about our block types.

Two rules shape the output:

1. **Data lives in the data model, not in the component tree.** Components
   carry `{"path": "/blocks/0/series"}` bindings rather than inline values, so
   a later `updateDataModel` can change what a card shows without resending
   the card. That is the whole point of A2UI's binding layer.
2. **Layout is composed from the basic catalog.** Cards, Columns, Rows and
   Buttons come from A2UI's standard catalog; only the six data-visualisation
   components are ours. A client that swapped our catalog for a different
   chart library would still render the structure.

Protocol note: we target v0.9 rather than the v1.0 candidate because v0.9 is
the current production spec and the only version `@a2ui/react` implements
natively today.
"""

from __future__ import annotations

from typing import Any, Iterable

from schemas import (
    BarChart,
    Block,
    BlockAction,
    DataTable,
    DonutChart,
    LineChart,
    StatCard,
    TextNote,
)

VERSION = "v0.9"

# Our custom catalog: the six financial components, layered on top of A2UI's
# basic catalog. The client registers the matching implementations under this
# same id; it is an identifier, not a URL that gets fetched.
CATALOG_ID = "https://acme.analytics/catalogs/finance/v1.json"

# The action name every generated button sends back. One name keeps the
# client-to-server contract small: the interesting part is the context.
REFINE_ACTION = "refine"

MAX_SERIES = 4
MAX_POINTS = 24
MAX_SLICES = 6
MAX_ROWS = 25
MAX_BLOCKS = 4
MAX_ACTIONS = 2

# Which block types render as a narrow tile. Consecutive tiles are packed into
# a Row so four KPIs read as one band instead of four stacked cards.
TILE_TYPES = {"stat_card"}


# --- message builders -----------------------------------------------------


def create_surface(surface_id: str) -> dict:
    """Open a surface.

    v0.9's `createSurface` is strict and carries no payload beyond the ids --
    inline `components` and `dataModel` are a v1.0 addition, and sending them
    here would be silently dropped, leaving the surface stuck on its
    placeholder. Content always arrives as separate update messages.
    """
    return {
        "version": VERSION,
        "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID},
    }


def update_components(surface_id: str, components: list[dict]) -> dict:
    return {
        "version": VERSION,
        "updateComponents": {"surfaceId": surface_id, "components": components},
    }


def update_data_model(surface_id: str, path: str, value: Any) -> dict:
    return {
        "version": VERSION,
        "updateDataModel": {"surfaceId": surface_id, "path": path, "value": value},
    }


# A2UI's fourth server-to-client message, `deleteSurface`, has no builder here
# on purpose: dismissal is a user action with no server involvement, so the
# client constructs that one message itself rather than asking us for it.


def bind(path: str) -> dict:
    """A data-model binding, the `{"path": ...}` form A2UI resolves at render."""
    return {"path": path}


# --- block sanitising -----------------------------------------------------


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


# --- the compiler ---------------------------------------------------------

# Block type -> the component name in our catalog, and the data-model keys it
# binds. Adding a component means one row here plus one React implementation.
_VIEW = {
    "stat_card": (
        "StatCard",
        ("title", "value", "unit", "delta_pct", "delta_direction", "caption"),
    ),
    "line_chart": ("LineChart", ("series", "unit", "x_label", "y_label")),
    "bar_chart": ("BarChart", ("series", "unit", "x_label", "y_label", "stacked")),
    "donut_chart": ("DonutChart", ("slices", "unit")),
    "data_table": ("DataTable", ("columns", "rows")),
    "text_note": ("TextNote", ("body",)),
}


def block_data(block: Block) -> dict:
    """The block's values, as they are stored in the surface data model."""
    data = block.model_dump(mode="json")
    data.pop("actions", None)
    data.pop("type", None)
    return data


def _action_components(block_id: str, actions: Iterable[BlockAction]) -> tuple[list[dict], str | None]:
    """Buttons that post a `refine` action back to the agent.

    The prompt travels in the action context rather than in the action name so
    the agent needs exactly one handler regardless of what the model invents.
    """
    actions = list(actions)
    if not actions:
        return [], None

    components: list[dict] = []
    button_ids: list[str] = []

    for index, action in enumerate(actions):
        button_id = f"{block_id}_a{index}"
        label_id = f"{button_id}_label"
        button_ids.append(button_id)
        components.append(
            {
                "id": button_id,
                "component": "Button",
                "child": label_id,
                "variant": "default",
                "action": {
                    "event": {
                        "name": REFINE_ACTION,
                        "context": {"prompt": action.prompt, "label": action.label},
                    }
                },
            }
        )
        components.append({"id": label_id, "component": "Text", "text": action.label})

    row_id = f"{block_id}_actions"
    components.append(
        {"id": row_id, "component": "Row", "children": button_ids, "justify": "start"}
    )
    return components, row_id


def compile_block(block: Block, index: int) -> list[dict]:
    """One block -> the A2UI components that draw it, bound to /blocks/{index}.

    Returns a flat component list; the caller is responsible for referencing
    `b{index}` from the root's children.
    """
    block_id = f"b{index}"
    base = f"/blocks/{index}"
    view_name, fields = _VIEW[block.type]

    components: list[dict] = []

    # Card -> Column(title, view, actions?)
    title_id = f"{block_id}_title"
    view_id = f"{block_id}_view"
    body_id = f"{block_id}_body"

    components.append({"id": block_id, "component": "Card", "child": body_id})

    view: dict[str, Any] = {"id": view_id, "component": view_name}
    for field in fields:
        view[field] = bind(f"{base}/{field}")
    components.append(view)

    action_components, actions_row_id = _action_components(block_id, block.actions)
    components.extend(action_components)

    # A stat card's title IS its heading, rendered inside the tile; anything
    # else gets a heading above the view.
    children = [] if block.type in TILE_TYPES else [title_id]
    if children:
        components.append(
            {"id": title_id, "component": "Text", "text": bind(f"{base}/title"), "variant": "h4"}
        )
    children.append(view_id)
    if actions_row_id:
        children.append(actions_row_id)
    components.append({"id": body_id, "component": "Column", "children": children})

    return components


def group_children(blocks: list[Block]) -> tuple[list[dict], list[str], set[str]]:
    """Pack consecutive stat cards into Rows; everything else is full width.

    Returns the extra Row components, the root's children in order, and the ids
    of the cards that landed inside a Row -- those need a `weight` so they share
    the width instead of huddling at the left edge.
    """
    extra: list[dict] = []
    children: list[str] = []
    in_row: set[str] = set()
    run: list[str] = []
    row_index = 0

    def flush() -> None:
        nonlocal run, row_index
        if not run:
            return
        if len(run) == 1:
            children.append(run[0])
        else:
            row_id = f"tilerow{row_index}"
            extra.append(
                {"id": row_id, "component": "Row", "children": list(run), "align": "stretch"}
            )
            children.append(row_id)
            in_row.update(run)
            row_index += 1
        run = []

    for index, block in enumerate(blocks):
        block_id = f"b{index}"
        if block.type in TILE_TYPES:
            run.append(block_id)
        else:
            flush()
            children.append(block_id)

    flush()
    return extra, children, in_row


def root_component(children: list[str]) -> dict:
    return {"id": "root", "component": "Column", "children": children}


def component_tree(blocks: list[Block]) -> list[dict]:
    """Every component needed to draw `blocks`, root included."""
    components: list[dict] = []
    for index, block in enumerate(blocks):
        components.extend(compile_block(block, index))

    rows, children, in_row = group_children(blocks)

    # `weight` is A2UI's flex-grow, and it is only legal on a direct child of a
    # Row or Column -- hence applying it here, once the grouping is known,
    # rather than when the card was built.
    for component in components:
        if component["id"] in in_row:
            component["weight"] = 1

    components.extend(rows)
    components.append(root_component(children))
    return components


def data_model(blocks: list[Block]) -> dict:
    """The surface data model the component bindings resolve against."""
    return {"blocks": [block_data(block) for block in blocks]}


def full_surface(surface_id: str, blocks: list[Block]) -> list[dict]:
    """A complete surface as a batch, for content that needs no streaming.

    Data before components, so no binding ever resolves against an empty model.
    """
    return [
        create_surface(surface_id),
        update_data_model(surface_id, "/", data_model(blocks)),
        update_components(surface_id, component_tree(blocks)),
    ]

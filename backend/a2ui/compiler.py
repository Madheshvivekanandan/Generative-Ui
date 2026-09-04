"""The block -> A2UI compiler.

Two rules shape the output:

1. **Data lives in the data model, not in the component tree.** Components
   carry `{"path": "/blocks/0/series"}` bindings rather than inline values, so
   a later `updateDataModel` can change what a card shows without resending
   the card. That is the whole point of A2UI's binding layer.
2. **Layout is composed from the basic catalog.** Cards, Columns, Rows and
   Buttons come from A2UI's standard catalog; only the six data-visualisation
   components are ours.

Nothing downstream of this package knows about our block types.
"""

from __future__ import annotations

from typing import Any, Iterable

from a2ui.constants import REFINE_ACTION, TILE_TYPES
from a2ui.messages import bind, create_surface, update_components, update_data_model
from schemas import Block, BlockAction

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


def _action_components(
    block_id: str, actions: Iterable[BlockAction]
) -> tuple[list[dict], str | None]:
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

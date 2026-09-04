"""A2UI v0.9 wire format: message builders, the sanitizer, and the compiler.

The agent plans in the typed blocks from `schemas`; everything the browser
actually receives is emitted here as genuine A2UI v0.9 messages
(`createSurface`, `updateComponents`, `updateDataModel`, `deleteSurface`),
which `@a2ui/react` renders directly.

Protocol note: we target v0.9 rather than the v1.0 candidate because v0.9 is
the current production spec and the only version `@a2ui/react` implements
natively today.

The package re-exports its public surface, so callers write `import a2ui` and
use `a2ui.sanitize(...)` without caring which module a function lives in.
"""

from a2ui.compiler import (
    block_data,
    compile_block,
    component_tree,
    data_model,
    full_surface,
    group_children,
    root_component,
)
from a2ui.constants import (
    CATALOG_ID,
    MAX_ACTIONS,
    MAX_BLOCKS,
    MAX_POINTS,
    MAX_ROWS,
    MAX_SERIES,
    MAX_SLICES,
    REFINE_ACTION,
    TILE_TYPES,
    VERSION,
)
from a2ui.messages import bind, create_surface, update_components, update_data_model
from a2ui.sanitizer import sanitize, text_note

__all__ = [
    "CATALOG_ID",
    "MAX_ACTIONS",
    "MAX_BLOCKS",
    "MAX_POINTS",
    "MAX_ROWS",
    "MAX_SERIES",
    "MAX_SLICES",
    "REFINE_ACTION",
    "TILE_TYPES",
    "VERSION",
    "bind",
    "block_data",
    "compile_block",
    "component_tree",
    "create_surface",
    "data_model",
    "full_surface",
    "group_children",
    "root_component",
    "sanitize",
    "text_note",
    "update_components",
    "update_data_model",
]

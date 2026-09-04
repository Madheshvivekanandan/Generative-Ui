"""Builders for the A2UI v0.9 envelope messages the backend sends."""

from __future__ import annotations

from typing import Any

from a2ui.constants import CATALOG_ID, VERSION


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

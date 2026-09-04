from __future__ import annotations

import a2ui
import baseline
from api.streams import CANVAS_SURFACE
from fastapi import APIRouter
from mock_data import dashboard_payload
from schemas import DashboardResponse

router = APIRouter()


@router.get("/api/dashboard", response_model=DashboardResponse, summary="The mock dataset")
def dashboard() -> DashboardResponse:
    """The raw mock dataset. Kept for `curl` and `/docs`; the UI uses the A2UI form."""
    return DashboardResponse.model_validate(dashboard_payload())


@router.get("/api/dashboard/a2ui", summary="The baseline dashboard as A2UI messages")
def dashboard_a2ui() -> dict:
    """The load-time dashboard, compiled by the same path a generated turn takes.

    It arrives in one batch rather than a stream because none of it is being
    composed live -- but it fills the same canvas surface the agent re-composes,
    through the same compiler, which is the point.
    """
    return {
        "surface_id": CANVAS_SURFACE,
        "messages": a2ui.full_surface(CANVAS_SURFACE, baseline.blocks()),
    }

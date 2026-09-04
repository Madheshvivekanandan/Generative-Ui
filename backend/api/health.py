from __future__ import annotations

import os

import a2ui
import agent
from fastapi import APIRouter
from schemas import HealthResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse, summary="Liveness and configuration")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=agent.MODEL,
        openai_key_set=bool(os.getenv("OPENAI_API_KEY")),
        protocol=a2ui.VERSION,
        catalog_id=a2ui.CATALOG_ID,
    )

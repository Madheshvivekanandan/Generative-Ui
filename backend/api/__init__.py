"""The HTTP layer: one router per route family, aggregated here."""

from fastapi import APIRouter

from api.dashboard import router as dashboard_router
from api.generate import router as generate_router
from api.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(dashboard_router)
api_router.include_router(generate_router)

__all__ = ["api_router"]

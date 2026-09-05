from fastapi import APIRouter

from app.api.exchange_rates import router as exchange_rates_router
from app.api.health import router as health_router
from app.api.transactions import router as transactions_router

router = APIRouter()
router.include_router(health_router)
router.include_router(exchange_rates_router)
router.include_router(transactions_router)

__all__ = ["router"]

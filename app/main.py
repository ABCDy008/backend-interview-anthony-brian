from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api import router
from app.database import engine

__all__ = ["app", "engine"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title="FX Money Changer API",
    summary="Daily exchange rates and foreign-exchange transaction recording.",
    description=(
        "A money changer API for managing daily ISO 4217 exchange rates and recording "
        "BUY, SELL, and cross-sell transactions. Transactions snapshot the rate used, "
        "apply banker’s rounding, and record fixed PHP fees. No customer PII is stored.\n\n"
        "Use the interactive Swagger UI at `/` or `/docs`. The machine-readable OpenAPI "
        "document is available at `/openapi.json`."
    ),
    version="0.1.0",
    docs_url="/",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "health",
            "description": "Service availability checks.",
        },
        {
            "name": "exchange-rates",
            "description": "Create, inspect, update, and delete daily BUY and SELL rates.",
        },
        {
            "name": "transactions",
            "description": (
                "Record and manage transactions. BUY charges a fixed PHP 1.00 fee; "
                "SELL charges a fixed PHP 0.50 fee. Cross-sell applies both fees."
            ),
        },
    ],
    lifespan=lifespan,
)


@app.get("/docs", include_in_schema=False)
def docs_alias() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=307)


app.include_router(router)
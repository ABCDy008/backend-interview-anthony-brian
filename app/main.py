from contextlib import asynccontextmanager
from collections import OrderedDict

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
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
            "description": (
                "Manage daily BUY and SELL rate resources. Collection endpoints return "
                "lists, and the business-key resource path finds one rate. Batch "
                "endpoints support daily ingestion and replacement."
            ),
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


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    app.openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        summary=app.summary,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    preferred_paths = [
        "/health",
        "/ready",
        "/exchange-rates",
        "/exchange-rates/batch",
        "/exchange-rates/{rate_date}/{base_currency}",
        "/exchange-rates/{rate_date}/{base_currency}/{target_currency}/{side}",
        "/transactions",
        "/transactions/buy",
        "/transactions/sell",
        "/transactions/cross-sell",
        "/transactions/{transaction_id}",
    ]
    path_order = {path: index for index, path in enumerate(preferred_paths)}
    app.openapi_schema["paths"] = OrderedDict(
        sorted(
            app.openapi_schema["paths"].items(),
            key=lambda item: (path_order.get(item[0], len(path_order)), item[0]),
        )
    )
    return app.openapi_schema


app.openapi = custom_openapi
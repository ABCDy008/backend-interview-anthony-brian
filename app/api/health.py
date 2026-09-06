from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ready"] = "ready"
    database: Literal["ok"] = "ok"


class ErrorResponse(BaseModel):
    detail: str


@router.get(
    "/health",
    tags=["health"],
    summary="Check API health",
    description=(
        "Returns HTTP 200 when the API process is available. This is a liveness check; "
        "it does not verify database connectivity or dependency health."
    ),
    response_model=HealthResponse,
    response_description="The API process is available.",
    responses={
        200: {
            "description": "The API process is available.",
            "content": {"application/json": {"example": {"status": "ok"}}},
        }
    },
)
def health() -> HealthResponse:
    return {"status": "ok"}


@router.get(
    "/ready",
    tags=["health"],
    summary="Check API readiness",
    description=(
        "Returns HTTP 200 when the API can reach its database. Returns HTTP 503 when "
        "the API process is running but the database is unavailable."
    ),
    response_model=ReadinessResponse,
    response_description="The API and its database dependency are ready.",
    responses={
        200: {
            "description": "The API and database are ready.",
            "content": {
                "application/json": {
                    "example": {"status": "ready", "database": "ok"}
                }
            },
        },
        503: {
            "model": ErrorResponse,
            "description": "The API is running but the database is unavailable.",
            "content": {
                "application/json": {
                    "example": {"detail": "Database is unavailable."}
                }
            },
        },
    },
)
def ready() -> ReadinessResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from None
    return {"status": "ready", "database": "ok"}

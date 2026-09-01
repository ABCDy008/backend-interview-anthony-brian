from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import USDExchangeRate
from app.schemas import (
    RateCreate,
    TransactionCreate,
    TransactionResponse,
    USDExchangeRateResponse,
)
from app.services import create_transaction, upsert_usd_exchange_rate

router = APIRouter()


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/rates",
    response_model=USDExchangeRateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["rates"],
)
def create_or_update_rate(
    payload: RateCreate, session: Session = Depends(get_db)
):
    return upsert_usd_exchange_rate(session, payload)


@router.get("/rates", response_model=list[USDExchangeRateResponse], tags=["rates"])
def list_rates(
    rate_date: date = Query(..., description="Date when the rates were last updated"),
    session: Session = Depends(get_db),
):
    return session.scalars(
        select(USDExchangeRate)
        .where(func.date(USDExchangeRate.last_updated_at) == rate_date)
        .order_by(USDExchangeRate.currency_code)
    ).all()


@router.get("/rates/{rate_id}", response_model=USDExchangeRateResponse, tags=["rates"])
def get_rate(rate_id: UUID, session: Session = Depends(get_db)):
    rate = session.get(USDExchangeRate, rate_id)
    if rate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rate not found")
    return rate


@router.put("/rates/{rate_id}", response_model=USDExchangeRateResponse, tags=["rates"])
def update_rate(
    rate_id: UUID, payload: RateCreate, session: Session = Depends(get_db)
):
    rate = session.get(USDExchangeRate, rate_id)
    if rate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rate not found")
    rate.currency_code = payload.currency_code
    rate.currency_name = payload.currency_name
    rate.rate_per_usd = payload.rate_per_usd
    session.commit()
    session.refresh(rate)
    return rate


@router.delete("/rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["rates"])
def delete_rate(rate_id: UUID, session: Session = Depends(get_db)):
    rate = session.get(USDExchangeRate, rate_id)
    if rate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rate not found")
    session.delete(rate)
    session.commit()


@router.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["transactions"],
)
def create_fx_transaction(payload: TransactionCreate, session: Session = Depends(get_db)):
    return create_transaction(session, payload)

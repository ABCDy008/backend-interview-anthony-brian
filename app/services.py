from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import calculator_for
from app.models import DailyRate, FXTransaction, TradeSide, USDExchangeRate
from app.schemas import DailyRateCreate, RateCreate, TransactionCreate


def find_rate(
    session: Session,
    *,
    rate_date: date,
    base_currency: str,
    quote_currency: str,
    side: TradeSide,
) -> DailyRate:
    rate = session.scalar(
        select(DailyRate).where(
            DailyRate.rate_date == rate_date,
            DailyRate.base_currency == base_currency,
            DailyRate.quote_currency == quote_currency,
            DailyRate.side == side,
        )
    )
    if rate is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="daily rate not found")
    return rate


def upsert_rate(session: Session, payload: DailyRateCreate) -> DailyRate:
    existing = session.scalar(
        select(DailyRate).where(
            DailyRate.rate_date == payload.rate_date,
            DailyRate.base_currency == payload.base_currency,
            DailyRate.quote_currency == payload.quote_currency,
            DailyRate.side == payload.side,
        )
    )
    if existing:
        existing.rate = payload.rate
        rate = existing
    else:
        rate = DailyRate(
            rate_date=payload.rate_date,
            base_currency=payload.base_currency,
            quote_currency=payload.quote_currency,
            side=TradeSide(payload.side),
            rate=payload.rate,
        )
        session.add(rate)
    session.commit()
    session.refresh(rate)
    return rate


def upsert_usd_exchange_rate(
    session: Session, payload: RateCreate
) -> USDExchangeRate:
    rate = session.scalar(
        select(USDExchangeRate).where(
            USDExchangeRate.currency_code == payload.currency_code
        )
    )
    if rate is None:
        rate = USDExchangeRate(
            id=uuid4(),
            currency_code=payload.currency_code,
            currency_name=payload.currency_name,
            rate_per_usd=payload.rate_per_usd,
        )
        session.add(rate)
    else:
        rate.currency_name = payload.currency_name
        rate.rate_per_usd = payload.rate_per_usd
    rate.last_updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(rate)
    return rate


def create_transaction(session: Session, payload: TransactionCreate) -> FXTransaction:
    rate = find_rate(
        session,
        rate_date=payload.transaction_timestamp.date(),
        base_currency=payload.base_currency,
        quote_currency=payload.quote_currency,
        side=TradeSide(payload.side),
    )
    result = calculator_for(rate.side.value, Decimal(rate.rate)).calculate(
        foreign_amount=payload.foreign_amount,
        base_amount=payload.base_amount,
    )
    transaction = FXTransaction(
        transaction_timestamp=payload.transaction_timestamp,
        base_currency=payload.base_currency,
        quote_currency=payload.quote_currency,
        side=rate.side,
        foreign_amount=result.foreign_amount,
        base_amount=result.base_amount,
        effective_rate=rate.rate,
        fee_amount=result.fee_amount,
        rounding_adjustment=result.rounding_adjustment,
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction

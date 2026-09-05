from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ExchangeRate
from app.schemas import (
    ExchangeRateBatchCreate,
    ExchangeRateBatchUpdate,
    ExchangeRateCreate,
)


class DuplicateExchangeRateError(Exception):
    pass


def list_exchange_rates(
    session: Session,
    *,
    rate_date: date | None = None,
    base_currency: str | None = None,
    target_currency: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> Sequence[ExchangeRate]:
    statement = select(ExchangeRate).order_by(
        ExchangeRate.rate_date.desc(),
        ExchangeRate.base_currency,
        ExchangeRate.target_currency,
    )
    if rate_date is not None:
        statement = statement.where(ExchangeRate.rate_date == rate_date)
    if base_currency is not None:
        statement = statement.where(ExchangeRate.base_currency == base_currency)
    if target_currency is not None:
        statement = statement.where(ExchangeRate.target_currency == target_currency)
    return session.scalars(statement.offset(offset).limit(limit)).all()


def get_exchange_rate(session: Session, rate_id: UUID) -> ExchangeRate | None:
    return session.get(ExchangeRate, rate_id)


def create_exchange_rate(session: Session, payload: ExchangeRateCreate) -> ExchangeRate:
    rate = ExchangeRate(**payload.model_dump())
    session.add(rate)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateExchangeRateError from error
    session.refresh(rate)
    return rate


def create_exchange_rate_batch(
    session: Session,
    payload: ExchangeRateBatchCreate,
) -> list[ExchangeRate]:
    rates = [
        ExchangeRate(
            rate_date=payload.rate_date,
            base_currency=payload.base_currency,
            target_currency=item.target_currency,
            exchange_rate=item.exchange_rate,
        )
        for item in payload.rates
    ]
    session.add_all(rates)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateExchangeRateError from error
    for rate in rates:
        session.refresh(rate)
    return rates


def replace_exchange_rate_batch(
    session: Session,
    rate_date: date,
    payload: ExchangeRateBatchUpdate,
) -> list[ExchangeRate]:
    existing_rates = session.scalars(
        select(ExchangeRate).where(
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.base_currency == payload.base_currency,
        )
    ).all()
    existing_by_target = {rate.target_currency: rate for rate in existing_rates}
    submitted_targets = {item.target_currency for item in payload.rates}

    for rate in existing_rates:
        if rate.target_currency not in submitted_targets:
            session.delete(rate)

    rates = []
    for item in payload.rates:
        rate = existing_by_target.get(item.target_currency)
        if rate is None:
            rate = ExchangeRate(
                rate_date=rate_date,
                base_currency=payload.base_currency,
                target_currency=item.target_currency,
                exchange_rate=item.exchange_rate,
            )
            session.add(rate)
        else:
            rate.exchange_rate = item.exchange_rate
        rates.append(rate)

    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateExchangeRateError from error
    for rate in rates:
        session.refresh(rate)
    return rates


def delete_exchange_rate_batch(
    session: Session,
    rate_date: date,
    base_currency: str,
) -> int:
    rates = session.scalars(
        select(ExchangeRate).where(
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.base_currency == base_currency,
        )
    ).all()
    for rate in rates:
        session.delete(rate)
    session.commit()
    return len(rates)


def update_exchange_rate(
    session: Session,
    rate: ExchangeRate,
    payload: ExchangeRateCreate,
) -> ExchangeRate:
    for field, value in payload.model_dump().items():
        setattr(rate, field, value)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateExchangeRateError from error
    session.refresh(rate)
    return rate


def delete_exchange_rate(session: Session, rate: ExchangeRate) -> None:
    session.delete(rate)
    session.commit()

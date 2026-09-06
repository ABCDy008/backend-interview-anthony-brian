from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ExchangeRate
from app.schemas.exchange_rates import (
    ExchangeRateBatchCreate,
    ExchangeRateBatchUpdate,
    ExchangeRateValueUpdate,
)


class DuplicateExchangeRateError(Exception):
    """Signal that an exchange-rate key already exists."""


class ExchangeRateBatchNotFoundError(Exception):
    """Signal that a requested daily exchange-rate set does not exist."""


def list_exchange_rates(
    session: Session,
    *,
    rate_date: date | None = None,
    base_currency: str | None = None,
    target_currency: str | None = None,
    side: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> Sequence[ExchangeRate]:
    """Return exchange rates matching the supplied filters and pagination."""
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
    if side is not None:
        statement = statement.where(ExchangeRate.side == side)
    return session.scalars(statement.offset(offset).limit(limit)).all()


def get_exchange_rate_by_key(
    session: Session,
    *,
    rate_date: date,
    base_currency: str,
    target_currency: str,
    side: str,
) -> ExchangeRate | None:
    """Return one exchange rate by its complete business key."""
    return session.scalar(
        select(ExchangeRate).where(
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.base_currency == base_currency,
            ExchangeRate.target_currency == target_currency,
            ExchangeRate.side == side,
        )
    )


def create_exchange_rate_batch(
    session: Session,
    payload: ExchangeRateBatchCreate,
) -> list[ExchangeRate]:
    """Create and persist all rates in a daily rate set."""
    rates = [
        ExchangeRate(
            rate_date=payload.rate_date,
            base_currency=payload.base_currency,
            target_currency=item.target_currency,
            side=item.side,
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
    base_currency: str,
    payload: ExchangeRateBatchUpdate,
) -> list[ExchangeRate]:
    """Replace the rates in an existing daily rate set."""
    existing_rates = session.scalars(
        select(ExchangeRate).where(
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.base_currency == base_currency,
        )
    ).all()
    if not existing_rates:
        raise ExchangeRateBatchNotFoundError

    existing_by_pair = {(rate.target_currency, rate.side): rate for rate in existing_rates}
    submitted_pairs = {(item.target_currency, item.side) for item in payload.rates}
    for rate in existing_rates:
        if (rate.target_currency, rate.side) not in submitted_pairs:
            session.delete(rate)

    rates = []
    for item in payload.rates:
        rate = existing_by_pair.get((item.target_currency, item.side))
        if rate is None:
            rate = ExchangeRate(
                rate_date=rate_date,
                base_currency=base_currency,
                target_currency=item.target_currency,
                side=item.side,
                exchange_rate=item.exchange_rate,
            )
            session.add(rate)
        else:
            rate.side = item.side
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


def delete_exchange_rate_batch(session: Session, rate_date: date, base_currency: str) -> int:
    """Delete a daily rate set and return the number of removed records."""
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


def update_exchange_rate_by_key(
    session: Session,
    *,
    rate_date: date,
    base_currency: str,
    target_currency: str,
    side: str,
    payload: ExchangeRateValueUpdate,
) -> ExchangeRate | None:
    """Update one exchange-rate value identified by its complete business key."""
    rate = get_exchange_rate_by_key(
        session,
        rate_date=rate_date,
        base_currency=base_currency,
        target_currency=target_currency,
        side=side,
    )
    if rate is None:
        return None
    rate.exchange_rate = payload.exchange_rate
    session.commit()
    session.refresh(rate)
    return rate

from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain import calculator_for
from app.models import ExchangeRate, ForeignExchangeTransaction
from app.schemas import (
    ExchangeRateBatchCreate,
    ExchangeRateBatchUpdate,
    ExchangeRateCreate,
    ExchangeRateSide,
    ExchangeRateValueUpdate,
    ForeignExchangeTransactionCreate,
    ForeignExchangeTransactionUpdate,
)


class DuplicateExchangeRateError(Exception):
    pass


class MissingExchangeRateError(Exception):
    pass


def list_foreign_exchange_transactions(
    session: Session,
    *,
    transaction_id: UUID | None = None,
    transaction_timestamp: datetime | None = None,
    base_currency: str | None = None,
    target_currency: str | None = None,
    side: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> Sequence[ForeignExchangeTransaction]:
    statement = select(ForeignExchangeTransaction).order_by(
        ForeignExchangeTransaction.created_at.desc(),
        ForeignExchangeTransaction.id,
    )
    if transaction_id is not None:
        statement = statement.where(
            ForeignExchangeTransaction.transaction_id == transaction_id
        )
    if transaction_timestamp is not None:
        statement = statement.where(
            ForeignExchangeTransaction.transaction_timestamp == transaction_timestamp
        )
    if base_currency is not None:
        statement = statement.where(
            ForeignExchangeTransaction.base_currency == base_currency
        )
    if target_currency is not None:
        statement = statement.where(
            ForeignExchangeTransaction.target_currency == target_currency
        )
    if side is not None:
        statement = statement.where(ForeignExchangeTransaction.side == side)
    return session.scalars(statement.offset(offset).limit(limit)).all()


def get_foreign_exchange_transaction(
    session: Session,
    transaction_row_id: UUID,
) -> ForeignExchangeTransaction | None:
    return session.get(ForeignExchangeTransaction, transaction_row_id)


def create_foreign_exchange_transaction(
    session: Session,
    payload: ForeignExchangeTransactionCreate,
) -> list[ForeignExchangeTransaction]:
    home_currency = get_settings().home_currency
    if (
        payload.base_currency != home_currency
        and payload.target_currency != home_currency
    ):
        return _create_cross_currency_transaction(session, payload, home_currency)
    return [_create_single_leg_transaction(session, payload)]


def _create_single_leg_transaction(
    session: Session,
    payload: ForeignExchangeTransactionCreate,
) -> ForeignExchangeTransaction:
    rate = get_exchange_rate_by_key(
        session,
        rate_date=payload.transaction_timestamp.date(),
        base_currency=payload.base_currency,
        target_currency=payload.target_currency,
        side=payload.side,
    )
    if rate is None:
        raise MissingExchangeRateError

    calculation = calculator_for(rate.side, rate.exchange_rate).calculate(
        foreign_amount=payload.foreign_amount,
        base_amount=None,
    )
    transaction = ForeignExchangeTransaction(
        transaction_id=payload.transaction_id,
        transaction_timestamp=payload.transaction_timestamp,
        base_currency=payload.base_currency,
        target_currency=payload.target_currency,
        side=payload.side,
        effective_rate=rate.exchange_rate,
        foreign_amount=calculation.foreign_amount,
        base_amount=calculation.base_amount,
        rounded_amount=calculation.rounding_adjustment,
        fee=calculation.fee_amount,
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


def _create_cross_currency_transaction(
    session: Session,
    payload: ForeignExchangeTransactionCreate,
    home_currency: str,
) -> list[ForeignExchangeTransaction]:
    """Neither currency is the home currency, so route the trade through it:
    BUY payload.base_currency for home_currency, then SELL payload.target_currency
    for the home_currency proceeds. Persisted as two rows sharing one transaction_id.
    """
    buy_rate = get_exchange_rate_by_key(
        session,
        rate_date=payload.transaction_timestamp.date(),
        base_currency=home_currency,
        target_currency=payload.base_currency,
        side=ExchangeRateSide.BUY,
    )
    if buy_rate is None:
        raise MissingExchangeRateError

    sell_rate = get_exchange_rate_by_key(
        session,
        rate_date=payload.transaction_timestamp.date(),
        base_currency=home_currency,
        target_currency=payload.target_currency,
        side=ExchangeRateSide.SELL,
    )
    if sell_rate is None:
        raise MissingExchangeRateError

    buy_calculation = calculator_for(buy_rate.side, buy_rate.exchange_rate).calculate(
        foreign_amount=payload.foreign_amount,
        base_amount=None,
    )
    # SELL leg spends the home-currency proceeds of the BUY leg as its base_amount input.
    sell_calculation = calculator_for(sell_rate.side, sell_rate.exchange_rate).calculate(
        foreign_amount=None,
        base_amount=buy_calculation.base_amount,
    )

    # Two inserts can't both rely on the DB's uuidv7() default and still match.
    transaction_id = payload.transaction_id or uuid4()
    buy_leg = ForeignExchangeTransaction(
        transaction_id=transaction_id,
        transaction_timestamp=payload.transaction_timestamp,
        base_currency=home_currency,
        target_currency=payload.base_currency,
        side=ExchangeRateSide.BUY,
        effective_rate=buy_rate.exchange_rate,
        foreign_amount=buy_calculation.foreign_amount,
        base_amount=buy_calculation.base_amount,
        rounded_amount=buy_calculation.rounding_adjustment,
        fee=buy_calculation.fee_amount,
    )
    sell_leg = ForeignExchangeTransaction(
        transaction_id=transaction_id,
        transaction_timestamp=payload.transaction_timestamp,
        base_currency=home_currency,
        target_currency=payload.target_currency,
        side=ExchangeRateSide.SELL,
        effective_rate=sell_rate.exchange_rate,
        foreign_amount=sell_calculation.foreign_amount,
        base_amount=sell_calculation.base_amount,
        rounded_amount=sell_calculation.rounding_adjustment,
        fee=sell_calculation.fee_amount,
    )
    session.add_all([buy_leg, sell_leg])
    session.commit()
    session.refresh(buy_leg)
    session.refresh(sell_leg)
    return [buy_leg, sell_leg]


def update_foreign_exchange_transaction(
    session: Session,
    transaction: ForeignExchangeTransaction,
    payload: ForeignExchangeTransactionUpdate,
) -> ForeignExchangeTransaction:
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(transaction, field, value)
    session.commit()
    session.refresh(transaction)
    return transaction


def delete_foreign_exchange_transaction(
    session: Session,
    transaction: ForeignExchangeTransaction,
) -> None:
    session.delete(transaction)
    session.commit()


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


def get_exchange_rate_by_key(
    session: Session,
    *,
    rate_date: date,
    base_currency: str,
    target_currency: str,
    side: str,
) -> ExchangeRate | None:
    return session.scalar(
        select(ExchangeRate).where(
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.base_currency == base_currency,
            ExchangeRate.target_currency == target_currency,
            ExchangeRate.side == side,
        )
    )


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
    payload: ExchangeRateBatchUpdate,
) -> list[ExchangeRate]:
    existing_rates = session.scalars(
        select(ExchangeRate).where(
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.base_currency == payload.base_currency,
        )
    ).all()
    existing_by_pair = {
        (rate.target_currency, rate.side): rate for rate in existing_rates
    }
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
                base_currency=payload.base_currency,
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


def update_exchange_rate_by_key(
    session: Session,
    *,
    rate_date: date,
    base_currency: str,
    target_currency: str,
    side: str,
    payload: ExchangeRateValueUpdate,
) -> ExchangeRate | None:
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


def delete_exchange_rate(session: Session, rate: ExchangeRate) -> None:
    session.delete(rate)
    session.commit()


def delete_exchange_rate_by_key(
    session: Session,
    *,
    rate_date: date,
    base_currency: str,
    target_currency: str,
    side: str,
) -> bool:
    rate = get_exchange_rate_by_key(
        session,
        rate_date=rate_date,
        base_currency=base_currency,
        target_currency=target_currency,
        side=side,
    )
    if rate is None:
        return False
    session.delete(rate)
    session.commit()
    return True

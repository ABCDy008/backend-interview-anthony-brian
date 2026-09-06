from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain import calculator_for
from app.models import ForeignExchangeTransaction
from app.schemas.exchange_rates import ExchangeRateSide
from app.schemas.transactions import (
    BuyTransactionCreate,
    CrossSellTransactionCreate,
    ForeignExchangeTransactionCreate,
    SellTransactionCreate,
)
from app.services.exchange_rates import get_exchange_rate_by_key


class MissingExchangeRateError(Exception):
    """Signal that a transaction has no applicable exchange-rate snapshot."""


class InvalidTransactionOperationError(Exception):
    """Signal that a transaction operation violates a business rule."""


def list_foreign_exchange_transactions(
    session: Session,
    *,
    transaction_id: UUID | None = None,
    transaction_date: date | None = None,
    transaction_timestamp: datetime | None = None,
    base_currency: str | None = None,
    target_currency: str | None = None,
    side: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> Sequence[ForeignExchangeTransaction]:
    """Return transaction legs matching the supplied filters and pagination."""
    statement = select(ForeignExchangeTransaction).order_by(
        ForeignExchangeTransaction.created_at.desc(),
        ForeignExchangeTransaction.id,
    )
    if transaction_id is not None:
        statement = statement.where(ForeignExchangeTransaction.transaction_id == transaction_id)
    if transaction_date is not None:
        start = datetime.combine(
            transaction_date,
            time.min,
            tzinfo=ZoneInfo(get_settings().business_timezone),
        )
        statement = statement.where(
            ForeignExchangeTransaction.transaction_timestamp >= start,
            ForeignExchangeTransaction.transaction_timestamp < start + timedelta(days=1),
        )
    if transaction_timestamp is not None:
        statement = statement.where(
            ForeignExchangeTransaction.transaction_timestamp == transaction_timestamp
        )
    if base_currency is not None:
        statement = statement.where(ForeignExchangeTransaction.base_currency == base_currency)
    if target_currency is not None:
        statement = statement.where(ForeignExchangeTransaction.target_currency == target_currency)
    if side is not None:
        statement = statement.where(ForeignExchangeTransaction.side == side)
    return session.scalars(statement.offset(offset).limit(limit)).all()


def create_buy_transaction(session: Session, payload: BuyTransactionCreate):
    """Create one transaction leg for buying a foreign currency."""
    home_currency = get_settings().home_currency
    if payload.target_currency == home_currency:
        raise InvalidTransactionOperationError("target_currency must differ from the home currency")
    return [_create_single_leg_transaction(session, ForeignExchangeTransactionCreate(
        transaction_timestamp=payload.transaction_timestamp,
        base_currency=home_currency,
        target_currency=payload.target_currency,
        side=ExchangeRateSide.BUY,
        foreign_amount=payload.foreign_amount,
        base_amount=payload.base_amount,
    ))]


def create_sell_transaction(session: Session, payload: SellTransactionCreate):
    """Create one transaction leg for selling a foreign currency."""
    home_currency = get_settings().home_currency
    if payload.target_currency == home_currency:
        raise InvalidTransactionOperationError("target_currency must differ from the home currency")
    return [_create_single_leg_transaction(session, ForeignExchangeTransactionCreate(
        transaction_timestamp=payload.transaction_timestamp,
        base_currency=home_currency,
        target_currency=payload.target_currency,
        side=ExchangeRateSide.SELL,
        foreign_amount=payload.foreign_amount,
        base_amount=payload.base_amount,
    ))]


def create_cross_sell_transaction(session: Session, payload: CrossSellTransactionCreate):
    """Create linked BUY and SELL legs for a foreign-currency exchange."""
    home_currency = get_settings().home_currency
    if home_currency in (payload.source_currency, payload.target_currency):
        raise InvalidTransactionOperationError(
            "cross-sell transactions must use two non-home currencies"
        )
    return _create_cross_currency_transaction(
        session,
        transaction_timestamp=payload.transaction_timestamp,
        source_currency=payload.source_currency,
        target_currency=payload.target_currency,
        home_currency=home_currency,
        source_amount=payload.source_amount,
        target_amount=payload.target_amount,
    )


def _create_single_leg_transaction(session: Session, payload: ForeignExchangeTransactionCreate):
    """Calculate and persist one transaction leg using a rate snapshot."""
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
        base_amount=payload.base_amount,
    )
    transaction = ForeignExchangeTransaction(
        transaction_id=uuid4(),
        transaction_timestamp=payload.transaction_timestamp,
        base_currency=payload.base_currency,
        target_currency=payload.target_currency,
        side=payload.side,
        effective_rate=rate.exchange_rate,
        foreign_amount=calculation.foreign_amount,
        base_amount=calculation.base_amount,
        rounding_adjustment=calculation.rounding_adjustment,
        fee=calculation.fee_amount,
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


def _create_cross_currency_transaction(
    session: Session,
    *,
    transaction_timestamp: datetime,
    source_currency: str,
    target_currency: str,
    home_currency: str,
    source_amount: Decimal | None = None,
    target_amount: Decimal | None = None,
):
    """Calculate and persist linked transaction legs for a cross-sell operation."""
    buy_rate = get_exchange_rate_by_key(
        session, rate_date=transaction_timestamp.date(), base_currency=home_currency,
        target_currency=source_currency, side=ExchangeRateSide.BUY,
    )
    if buy_rate is None:
        raise MissingExchangeRateError
    sell_rate = get_exchange_rate_by_key(
        session, rate_date=transaction_timestamp.date(), base_currency=home_currency,
        target_currency=target_currency, side=ExchangeRateSide.SELL,
    )
    if sell_rate is None:
        raise MissingExchangeRateError

    buy_calculator = calculator_for(buy_rate.side, buy_rate.exchange_rate)
    sell_calculator = calculator_for(sell_rate.side, sell_rate.exchange_rate)
    if target_amount is None:
        buy_calculation = buy_calculator.calculate(
            foreign_amount=source_amount, base_amount=None, round_foreign=False, round_base=False
        )
        sell_calculation = sell_calculator.calculate(
            foreign_amount=None, base_amount=buy_calculation.base_amount
        )
    else:
        sell_calculation = sell_calculator.calculate(foreign_amount=target_amount, base_amount=None)
        buy_calculation = buy_calculator.calculate(
            foreign_amount=None, base_amount=sell_calculation.base_amount,
            round_foreign=False, round_base=False,
        )

    transaction_id = uuid4()
    buy_leg = ForeignExchangeTransaction(
        transaction_id=transaction_id, transaction_timestamp=transaction_timestamp,
        base_currency=home_currency, target_currency=source_currency,
        side=ExchangeRateSide.BUY, effective_rate=buy_rate.exchange_rate,
        foreign_amount=buy_calculation.foreign_amount, base_amount=buy_calculation.base_amount,
        rounding_adjustment=buy_calculation.rounding_adjustment, fee=buy_calculation.fee_amount,
    )
    sell_leg = ForeignExchangeTransaction(
        transaction_id=transaction_id, transaction_timestamp=transaction_timestamp,
        base_currency=home_currency, target_currency=target_currency,
        side=ExchangeRateSide.SELL, effective_rate=sell_rate.exchange_rate,
        foreign_amount=sell_calculation.foreign_amount, base_amount=sell_calculation.base_amount,
        rounding_adjustment=sell_calculation.rounding_adjustment, fee=sell_calculation.fee_amount,
    )
    session.add_all([buy_leg, sell_leg])
    session.commit()
    session.refresh(buy_leg)
    session.refresh(sell_leg)
    return [buy_leg, sell_leg]

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.domain import InsufficientAmountError
from app.schemas import (
    BuyTransactionCreate,
    CrossSellTransactionCreate,
    ExchangeRateSide,
    ForeignExchangeTransactionResponse,
    ForeignExchangeTransactionUpdate,
    SellTransactionCreate,
)
from app.services import (
    InvalidTransactionOperationError,
    MissingExchangeRateError,
    create_buy_transaction,
    create_cross_sell_transaction,
    create_sell_transaction,
    delete_foreign_exchange_transaction,
    get_foreign_exchange_transaction,
    list_foreign_exchange_transactions,
    update_foreign_exchange_transaction,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])
DbSession = Annotated[Session, Depends(get_db)]


def _transaction_conflict(error: MissingExchangeRateError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="No exchange rate exists for the requested date, currencies, and side.",
    )


def _invalid_operation(error: InvalidTransactionOperationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))


@router.get(
    "",
    response_model=list[ForeignExchangeTransactionResponse],
    summary="List transactions",
    description="List recorded transactions with optional timestamp, currency, side, and pagination filters.",
    response_description="The matching transactions.",
)
def list_transactions(
    session: DbSession,
    transaction_id: Annotated[UUID | None, Query()] = None,
    transaction_timestamp: Annotated[datetime | None, Query()] = None,
    base_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    side: ExchangeRateSide | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[ForeignExchangeTransactionResponse]:
    return list(
        list_foreign_exchange_transactions(
            session,
            transaction_id=transaction_id,
            transaction_timestamp=transaction_timestamp,
            base_currency=base_currency.upper() if base_currency else None,
            target_currency=target_currency.upper() if target_currency else None,
            side=side,
            offset=offset,
            limit=limit,
        )
    )


@router.get(
    "/{transaction_row_id}",
    response_model=ForeignExchangeTransactionResponse,
    summary="Get a transaction",
    description="Retrieve one recorded transaction by its database row UUID.",
    responses={404: {"description": "Transaction not found."}},
)
def get_transaction(
    transaction_row_id: UUID,
    session: DbSession,
) -> ForeignExchangeTransactionResponse:
    transaction = get_foreign_exchange_transaction(session, transaction_row_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foreign exchange transaction not found.",
        )
    return transaction


@router.post(
    "/buy",
    response_model=list[ForeignExchangeTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a BUY transaction",
    description=(
        "Record the store buying foreign currency from a customer. Provide exactly one of "
        "foreign_amount or base_amount. A fixed PHP 1.00 fee is deducted from the customer payout."
    ),
    responses={
        409: {"description": "No matching daily BUY rate exists."},
        422: {"description": "Invalid amounts or insufficient amount to cover the fee."},
    },
)
def create_buy(
    payload: BuyTransactionCreate,
    session: DbSession,
) -> list[ForeignExchangeTransactionResponse]:
    try:
        return create_buy_transaction(session, payload)
    except MissingExchangeRateError as error:
        raise _transaction_conflict(error) from None
    except InsufficientAmountError as error:
        raise _invalid_operation(error) from None
    except InvalidTransactionOperationError as error:
        raise _invalid_operation(error) from None


@router.post(
    "/sell",
    response_model=list[ForeignExchangeTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a SELL transaction",
    description=(
        "Record the store selling foreign currency to a customer. Provide exactly one of "
        "foreign_amount or base_amount. A fixed PHP 0.50 fee is added to the customer payment."
    ),
    responses={
        409: {"description": "No matching daily SELL rate exists."},
        422: {"description": "Invalid amounts or insufficient amount to cover the fee."},
    },
)
def create_sell(
    payload: SellTransactionCreate,
    session: DbSession,
) -> list[ForeignExchangeTransactionResponse]:
    try:
        return create_sell_transaction(session, payload)
    except MissingExchangeRateError as error:
        raise _transaction_conflict(error) from None
    except InsufficientAmountError as error:
        raise _invalid_operation(error) from None
    except InvalidTransactionOperationError as error:
        raise _invalid_operation(error) from None


@router.post(
    "/cross-sell",
    response_model=list[ForeignExchangeTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a cross-sell transaction",
    description=(
        "Convert between two foreign currencies through the configured home currency. "
        "Provide exactly one of source_amount or target_amount. Both the BUY PHP 1.00 "
        "and SELL PHP 0.50 fees apply."
    ),
    responses={
        409: {"description": "A required daily BUY or SELL rate is missing."},
        422: {"description": "Invalid amounts or insufficient amount to cover a fee."},
    },
)
def create_cross_sell(
    payload: CrossSellTransactionCreate,
    session: DbSession,
) -> list[ForeignExchangeTransactionResponse]:
    try:
        return create_cross_sell_transaction(session, payload)
    except MissingExchangeRateError as error:
        raise _transaction_conflict(error) from None
    except InsufficientAmountError as error:
        raise _invalid_operation(error) from None
    except InvalidTransactionOperationError as error:
        raise _invalid_operation(error) from None


@router.put(
    "/{transaction_row_id}",
    response_model=ForeignExchangeTransactionResponse,
    summary="Update a transaction",
    description="Replace editable fields on an existing transaction record.",
    responses={404: {"description": "Transaction not found."}},
)
def update_transaction(
    transaction_row_id: UUID,
    payload: ForeignExchangeTransactionUpdate,
    session: DbSession,
) -> ForeignExchangeTransactionResponse:
    transaction = get_foreign_exchange_transaction(session, transaction_row_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foreign exchange transaction not found.",
        )
    return update_foreign_exchange_transaction(session, transaction, payload)


@router.delete(
    "/{transaction_row_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a transaction",
    description="Delete an existing transaction record.",
    responses={404: {"description": "Transaction not found."}},
)
def delete_transaction(
    transaction_row_id: UUID,
    session: DbSession,
) -> Response:
    transaction = get_foreign_exchange_transaction(session, transaction_row_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foreign exchange transaction not found.",
        )
    delete_foreign_exchange_transaction(session, transaction)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ExchangeRateSide,
    ForeignExchangeTransactionCreate,
    ForeignExchangeTransactionResponse,
    ForeignExchangeTransactionUpdate,
)
from app.services import (
    MissingExchangeRateError,
    create_foreign_exchange_transaction,
    delete_foreign_exchange_transaction,
    get_foreign_exchange_transaction,
    list_foreign_exchange_transactions,
    update_foreign_exchange_transaction,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=list[ForeignExchangeTransactionResponse],
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
    "",
    response_model=list[ForeignExchangeTransactionResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(
    payload: ForeignExchangeTransactionCreate,
    session: DbSession,
) -> list[ForeignExchangeTransactionResponse]:
    try:
        return create_foreign_exchange_transaction(session, payload)
    except MissingExchangeRateError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No exchange rate exists for the requested date, currencies, and side.",
        ) from None


@router.put(
    "/{transaction_row_id}",
    response_model=ForeignExchangeTransactionResponse,
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

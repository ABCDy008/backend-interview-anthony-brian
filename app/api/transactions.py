from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api_docs.transactions import (
    buy_openapi_extra,
    cross_sell_openapi_extra,
    sell_openapi_extra,
)
from app.database import get_db
from app.domain import InsufficientAmountError
from app.schemas.transactions import (
    BuyTransactionCreate,
    CrossSellTransactionCreate,
    ExchangeRateSide,
    ForeignExchangeTransactionResponse,
    SellTransactionCreate,
)
from app.services.transactions import (
    InvalidTransactionOperationError,
    MissingExchangeRateError,
    create_buy_transaction,
    create_cross_sell_transaction,
    create_sell_transaction,
    list_foreign_exchange_transactions,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])
DbSession = Annotated[Session, Depends(get_db)]


class ValidationErrorItem(BaseModel):
    """Represent one structured request-validation error."""

    type: str
    loc: list[str | int]
    msg: str
    input: Any | None = None
    ctx: dict[str, Any] | None = None


class ValidationErrorResponse(BaseModel):
    """Represent the API validation-error response body."""

    detail: list[ValidationErrorItem]


class ErrorResponse(BaseModel):
    """Represent a plain API error response."""

    detail: str


def _transaction_conflict(error: MissingExchangeRateError) -> HTTPException:
    """Map a missing exchange rate to an HTTP conflict response."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="No exchange rate exists for the requested date, currencies, and side.",
    )


def _invalid_operation(error: InvalidTransactionOperationError) -> HTTPException:
    """Map an invalid transaction operation to an HTTP validation response."""
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))


@router.get(
    "",
    response_model=list[ForeignExchangeTransactionResponse],
    summary="List transactions",
    description=(
        "List immutable transaction legs with optional business date, exact timestamp, "
        "logical transaction ID, currency, side, and pagination filters. Use "
        "transaction_id to retrieve all legs for one logical transaction. The business "
        "date uses the configured store timezone. A cross-sell appears as two records "
        "sharing one transaction_id."
    ),
    response_description="The matching persisted transaction legs.",
    responses={
        200: {
            "description": "The matching persisted transaction legs.",
            "content": {
                "application/json": {
                    "examples": {
                        "singleLeg": {
                            "summary": "One BUY transaction",
                            "value": [
                                {
                                    "id": "0198f2b3-7c5a-7e01-8b2d-123456789abc",
                                    "transaction_id": "0198f2b3-7c5a-7e01-8b2d-123456789abd",
                                    "transaction_timestamp": "2026-09-06T10:30:00Z",
                                    "base_currency": "PHP",
                                    "target_currency": "USD",
                                    "side": "BUY",
                                    "effective_rate": "0.0161164831",
                                    "foreign_amount": "100.0000000000",
                                    "base_amount": "5825.0000000000",
                                    "rounding_adjustment": "0.0000000000",
                                    "fee": "1.0000000000",
                                    "created_at": "2026-09-06T10:30:01Z",
                                }
                            ],
                        },
                        "crossSell": {
                            "summary": "Both legs of a cross-sell",
                            "description": "A cross-sell returns two records sharing transaction_id.",
                            "value": [
                                {
                                    "id": "0198f2b3-7c5a-7e01-8b2d-123456789abc",
                                    "transaction_id": "0198f2b3-7c5a-7e01-8b2d-123456789abd",
                                    "transaction_timestamp": "2026-09-06T10:30:00Z",
                                    "base_currency": "PHP",
                                    "target_currency": "USD",
                                    "side": "BUY",
                                    "effective_rate": "0.0161164831",
                                    "foreign_amount": "100.0000000000",
                                    "base_amount": "5825.0000000000",
                                    "rounding_adjustment": "0.0000000000",
                                    "fee": "1.0000000000",
                                    "created_at": "2026-09-06T10:30:01Z",
                                },
                                {
                                    "id": "0198f2b3-7c5a-7e02-8b2d-123456789abe",
                                    "transaction_id": "0198f2b3-7c5a-7e01-8b2d-123456789abd",
                                    "transaction_timestamp": "2026-09-06T10:30:00Z",
                                    "base_currency": "PHP",
                                    "target_currency": "JPY",
                                    "side": "SELL",
                                    "effective_rate": "1.9500000000",
                                    "foreign_amount": "11358.9743589744",
                                    "base_amount": "22150.0000000000",
                                    "rounding_adjustment": "0.0000000000",
                                    "fee": "0.5000000000",
                                    "created_at": "2026-09-06T10:30:01Z",
                                },
                            ],
                        },
                        "noMatches": {
                            "summary": "No matching transactions",
                            "value": [],
                        },
                    }
                }
            },
        },
        422: {
            "model": ValidationErrorResponse,
            "description": "One or more query parameters are invalid.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "enum",
                                "loc": ["query", "side"],
                                "msg": "Input should be 'BUY' or 'SELL'",
                                "input": "HOLD",
                                "ctx": {"expected": "'BUY' or 'SELL'"},
                            }
                        ]
                    }
                }
            },
        },
    },
)
def list_transactions(
    session: DbSession,
    transaction_id: Annotated[UUID | None, Query()] = None,
    transaction_date: Annotated[date | None, Query()] = None,
    transaction_timestamp: Annotated[datetime | None, Query()] = None,
    base_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    side: ExchangeRateSide | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[ForeignExchangeTransactionResponse]:
    """List persisted transaction legs matching the supplied filters."""
    return list(
        list_foreign_exchange_transactions(
            session,
            transaction_id=transaction_id,
            transaction_date=transaction_date,
            transaction_timestamp=transaction_timestamp,
            base_currency=base_currency.upper() if base_currency else None,
            target_currency=target_currency.upper() if target_currency else None,
            side=side,
            offset=offset,
            limit=limit,
        )
    )


@router.post(
    "/purchases",
    response_model=list[ForeignExchangeTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a BUY transaction",
    description=(
        "Record the store buying foreign currency from a customer. Provide exactly one of "
        "foreign_amount or base_amount. A fixed PHP 1.00 fee is deducted from the customer payout. "
        "The response is a one-item list containing the persisted BUY leg."
    ),
    response_description="The persisted BUY transaction leg.",
    openapi_extra=buy_openapi_extra(),
    responses={
        201: {
            "description": "The BUY transaction was recorded.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "0198f2b3-7c5a-7e01-8b2d-123456789abc",
                            "transaction_id": "0198f2b3-7c5a-7e01-8b2d-123456789abd",
                            "transaction_timestamp": "2026-09-06T10:30:00Z",
                            "base_currency": "PHP",
                            "target_currency": "USD",
                            "side": "BUY",
                            "effective_rate": "0.0161164831",
                            "foreign_amount": "100.0000000000",
                            "base_amount": "5825.0000000000",
                            "rounding_adjustment": "0.0000000000",
                            "fee": "1.0000000000",
                            "created_at": "2026-09-06T10:30:01Z",
                        }
                    ]
                }
            },
        },
        409: {
            "model": ErrorResponse,
            "description": "No matching daily BUY rate exists for the transaction date.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No exchange rate exists for the requested date, currencies, and side."
                    }
                }
            },
        },
        422: {
            "model": ValidationErrorResponse,
            "description": "The request is invalid, or the amount is insufficient after applying the fee.",
            "content": {
                "application/json": {
                    "examples": {
                        "bothAmountsProvided": {
                            "summary": "Exactly one amount is required",
                            "value": {
                                "detail": [
                                    {
                                        "type": "value_error",
                                        "loc": ["body"],
                                        "msg": "Value error, provide exactly one of foreign_amount or base_amount",
                                        "input": {
                                            "transaction_timestamp": "2026-09-06T10:30:00Z",
                                            "target_currency": "USD",
                                            "foreign_amount": "100",
                                            "base_amount": "5825",
                                        },
                                    }
                                ]
                            },
                        },
                        "invalidAmount": {
                            "summary": "Amount must be positive",
                            "value": {
                                "detail": [
                                    {
                                        "type": "greater_than",
                                        "loc": ["body", "foreign_amount"],
                                        "msg": "Input should be greater than 0",
                                        "input": "0",
                                        "ctx": {"gt": 0},
                                    }
                                ]
                            },
                        },
                    }
                }
            },
        },
    },
)
def create_buy(
    payload: BuyTransactionCreate,
    session: DbSession,
) -> list[ForeignExchangeTransactionResponse]:
    """Create a BUY transaction and return its persisted leg."""
    try:
        return create_buy_transaction(session, payload)
    except MissingExchangeRateError as error:
        raise _transaction_conflict(error) from None
    except InsufficientAmountError as error:
        raise _invalid_operation(error) from None
    except InvalidTransactionOperationError as error:
        raise _invalid_operation(error) from None


@router.post(
    "/sales",
    response_model=list[ForeignExchangeTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a SELL transaction",
    description=(
        "Record the store selling foreign currency to a customer. Provide exactly one of "
        "foreign_amount or base_amount. A fixed PHP 0.50 fee is added to the customer payment. "
        "The response is a one-item list containing the persisted SELL leg."
    ),
    response_description="The persisted SELL transaction leg.",
    openapi_extra=sell_openapi_extra(),
    responses={
        201: {
            "description": "The SELL transaction was recorded.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "0198f2b3-7c5a-7e01-8b2d-123456789abc",
                            "transaction_id": "0198f2b3-7c5a-7e01-8b2d-123456789abd",
                            "transaction_timestamp": "2026-09-06T10:30:00Z",
                            "base_currency": "PHP",
                            "target_currency": "USD",
                            "side": "SELL",
                            "effective_rate": "0.0157973449",
                            "foreign_amount": "100.0000000000",
                            "base_amount": "5910.0000000000",
                            "rounding_adjustment": "0.0000000000",
                            "fee": "0.5000000000",
                            "created_at": "2026-09-06T10:30:01Z",
                        }
                    ]
                }
            },
        },
        409: {
            "model": ErrorResponse,
            "description": "No matching daily SELL rate exists for the transaction date.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No exchange rate exists for the requested date, currencies, and side."
                    }
                }
            },
        },
        422: {
            "model": ValidationErrorResponse,
            "description": "The request is invalid, or the amount is insufficient after applying the fee.",
            "content": {
                "application/json": {
                    "examples": {
                        "bothAmountsProvided": {
                            "summary": "Exactly one amount is required",
                            "value": {
                                "detail": [
                                    {
                                        "type": "value_error",
                                        "loc": ["body"],
                                        "msg": "Value error, provide exactly one of foreign_amount or base_amount",
                                        "input": {
                                            "transaction_timestamp": "2026-09-06T10:30:00Z",
                                            "target_currency": "USD",
                                            "foreign_amount": "100",
                                            "base_amount": "5825",
                                        },
                                    }
                                ]
                            },
                        },
                        "invalidAmount": {
                            "summary": "Amount must be positive",
                            "value": {
                                "detail": [
                                    {
                                        "type": "greater_than",
                                        "loc": ["body", "base_amount"],
                                        "msg": "Input should be greater than 0",
                                        "input": "0",
                                        "ctx": {"gt": 0},
                                    }
                                ]
                            },
                        },
                    }
                }
            },
        },
    },
)
def create_sell(
    payload: SellTransactionCreate,
    session: DbSession,
) -> list[ForeignExchangeTransactionResponse]:
    """Create a SELL transaction and return its persisted leg."""
    try:
        return create_sell_transaction(session, payload)
    except MissingExchangeRateError as error:
        raise _transaction_conflict(error) from None
    except InsufficientAmountError as error:
        raise _invalid_operation(error) from None
    except InvalidTransactionOperationError as error:
        raise _invalid_operation(error) from None


@router.post(
    "/exchanges",
    response_model=list[ForeignExchangeTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a cross-sell transaction",
    description=(
        "Convert between two foreign currencies through the configured home currency. "
        "Provide exactly one of source_amount or target_amount. Both the BUY PHP 1.00 "
        "and SELL PHP 0.50 fees apply. The response contains two transaction legs: "
        "a BUY leg for source_currency and a SELL leg for target_currency. Both legs "
        "share the same transaction_id and are returned using the standard transaction "
        "response schema."
    ),
    response_description=(
        "The two persisted transaction legs, returned in execution order: BUY source "
        "currency, then SELL target currency."
    ),
    openapi_extra=cross_sell_openapi_extra(),
    responses={
        201: {
            "description": "Both cross-sell transaction legs were recorded.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "0198f2b3-7c5a-7e01-8b2d-123456789abc",
                            "transaction_id": "0198f2b3-7c5a-7e01-8b2d-123456789abd",
                            "transaction_timestamp": "2026-09-06T10:30:00Z",
                            "base_currency": "PHP",
                            "target_currency": "USD",
                            "side": "BUY",
                            "effective_rate": "0.0161164831",
                            "foreign_amount": "100.0000000000",
                            "base_amount": "5825.0000000000",
                            "rounding_adjustment": "0.0000000000",
                            "fee": "1.0000000000",
                            "created_at": "2026-09-06T10:30:01Z",
                        },
                        {
                            "id": "0198f2b3-7c5a-7e02-8b2d-123456789abe",
                            "transaction_id": "0198f2b3-7c5a-7e01-8b2d-123456789abd",
                            "transaction_timestamp": "2026-09-06T10:30:00Z",
                            "base_currency": "PHP",
                            "target_currency": "JPY",
                            "side": "SELL",
                            "effective_rate": "1.9500000000",
                            "foreign_amount": "11358.9743589744",
                            "base_amount": "22150.0000000000",
                            "rounding_adjustment": "0.0000000000",
                            "fee": "0.5000000000",
                            "created_at": "2026-09-06T10:30:01Z",
                        },
                    ]
                }
            },
        },
        409: {
            "model": ErrorResponse,
            "description": "A required daily BUY or SELL rate is missing.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No exchange rate exists for the requested date, currencies, and side."
                    }
                }
            },
        },
        422: {
            "model": ValidationErrorResponse,
            "description": "The request is invalid, or the amount is insufficient after applying a fee.",
            "content": {
                "application/json": {
                    "examples": {
                        "bothAmountsProvided": {
                            "summary": "Exactly one amount is required",
                            "value": {
                                "detail": [
                                    {
                                        "type": "value_error",
                                        "loc": ["body"],
                                        "msg": "Value error, provide exactly one of source_amount or target_amount",
                                        "input": {
                                            "transaction_timestamp": "2026-09-06T10:30:00Z",
                                            "source_currency": "USD",
                                            "target_currency": "JPY",
                                            "source_amount": "100",
                                            "target_amount": "10000",
                                        },
                                    }
                                ]
                            },
                        },
                        "sameCurrency": {
                            "summary": "Currencies must differ",
                            "value": {
                                "detail": [
                                    {
                                        "type": "value_error",
                                        "loc": ["body"],
                                        "msg": "Value error, source_currency and target_currency must differ",
                                        "input": {
                                            "transaction_timestamp": "2026-09-06T10:30:00Z",
                                            "source_currency": "USD",
                                            "target_currency": "USD",
                                            "source_amount": "100",
                                        },
                                    }
                                ]
                            },
                        },
                    }
                }
            },
        },
    },
)
def create_cross_sell(
    payload: CrossSellTransactionCreate,
    session: DbSession,
) -> list[ForeignExchangeTransactionResponse]:
    """Create and return the BUY and SELL legs of a cross-sell transaction."""

    try:
        return create_cross_sell_transaction(session, payload)
    except MissingExchangeRateError as error:
        raise _transaction_conflict(error) from None
    except InsufficientAmountError as error:
        raise _invalid_operation(error) from None
    except InvalidTransactionOperationError as error:
        raise _invalid_operation(error) from None



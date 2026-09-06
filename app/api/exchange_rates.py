from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api_docs.exchange_rates import (
    batch_create_openapi_extra,
    batch_update_openapi_extra,
    value_update_openapi_extra,
)
from app.database import get_db
from app.schemas.exchange_rates import (
    ExchangeRateBatchCreate,
    ExchangeRateBatchDeleteResponse,
    ExchangeRateBatchResponse,
    ExchangeRateBatchUpdate,
    ExchangeRateResponse,
    ExchangeRateSide,
    ExchangeRateValueUpdate,
    normalize_currency_code,
)
from app.services.exchange_rates import (
    DuplicateExchangeRateError,
    ExchangeRateBatchNotFoundError,
    create_exchange_rate_batch,
    delete_exchange_rate_batch,
    get_exchange_rate_by_key,
    list_exchange_rates,
    replace_exchange_rate_batch,
    update_exchange_rate_by_key,
)

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])
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


# GET endpoints
@router.get(
    "",
    response_model=list[ExchangeRateResponse],
    summary="List exchange rates",
    description=(
        "List exchange-rate snapshots for the required rate_date. With only rate_date, "
        "the endpoint returns up to 20 rates by default. Add base_currency and "
        "target_currency to return both BUY and SELL rates for one currency pair. Add "
        "side=BUY or side=SELL to return one side of that pair. The endpoint always "
        "returns a collection: a matching single rate is returned as a one-item list, "
        "and no matches return an empty list. Invalid query values return 422."
    ),
    response_description=(
        "The matching exchange-rate snapshots, with a default limit of 20 and a maximum "
        "limit of 500."
    ),
    responses={
        200: {
            "description": (
                "Matching rates. The default date-only query returns up to 20 records; "
                "a currency pair returns BUY and SELL records; adding side returns one "
                "side as a one-item list. The maximum requested page size is 500."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "dateOnly": {
                            "summary": "All rates for a date",
                            "description": (
                                "GET /exchange-rates?rate_date=2026-09-06 returns up to "
                                "20 records by default."
                            ),
                            "value": [
                                {
                                    "id": "0198f2b3-7c5a-7e01-8b2d-123456789abc",
                                    "rate_date": "2026-09-06",
                                    "base_currency": "PHP",
                                    "target_currency": "USD",
                                    "side": "BUY",
                                       "exchange_rate": "0.0161164831",
                                    "created_at": "2026-09-06T00:00:00Z",
                                },
                                {
                                    "id": "0198f2b3-7c5a-7e02-8b2d-123456789abd",
                                    "rate_date": "2026-09-06",
                                    "base_currency": "PHP",
                                    "target_currency": "USD",
                                    "side": "SELL",
                                       "exchange_rate": "0.0157973449",
                                    "created_at": "2026-09-06T00:00:00Z",
                                },
                            ],
                        },
                        "currencyPair": {
                            "summary": "Both sides for one currency pair",
                            "description": (
                                "GET /exchange-rates?rate_date=2026-09-06&"
                                "base_currency=PHP&target_currency=USD returns the BUY "
                                "and SELL rates for PHP/USD."
                            ),
                            "value": [
                                {
                                    "id": "0198f2b3-7c5a-7e01-8b2d-123456789abc",
                                    "rate_date": "2026-09-06",
                                    "base_currency": "PHP",
                                    "target_currency": "USD",
                                    "side": "BUY",
                                       "exchange_rate": "0.0161164831",
                                    "created_at": "2026-09-06T00:00:00Z",
                                },
                                {
                                    "id": "0198f2b3-7c5a-7e02-8b2d-123456789abd",
                                    "rate_date": "2026-09-06",
                                    "base_currency": "PHP",
                                    "target_currency": "USD",
                                    "side": "SELL",
                                       "exchange_rate": "0.0157973449",
                                    "created_at": "2026-09-06T00:00:00Z",
                                },
                            ],
                        },
                        "singleSide": {
                            "summary": "One side for one currency pair",
                            "description": (
                                "GET /exchange-rates?rate_date=2026-09-06&"
                                "base_currency=PHP&target_currency=USD&side=BUY "
                                "returns one BUY rate in a one-item list."
                            ),
                            "value": [
                                {
                                    "id": "0198f2b3-7c5a-7e01-8b2d-123456789abc",
                                    "rate_date": "2026-09-06",
                                    "base_currency": "PHP",
                                    "target_currency": "USD",
                                    "side": "BUY",
                                       "exchange_rate": "0.0161164831",
                                    "created_at": "2026-09-06T00:00:00Z",
                                }
                            ],
                        },
                        "noMatches": {
                            "summary": "No matching rates",
                            "description": (
                                "A valid query with no matching rates returns 200 with "
                                "an empty list."
                            ),
                            "value": [],
                        },
                    }
                }
            },
        },
        422: {
            "model": ValidationErrorResponse,
            "description": (
                "The query parameters are invalid. This includes a missing or malformed "
                "rate_date, invalid currency-code length, unsupported side, negative "
                "offset, or a limit outside the range 1 to 500."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "invalidSide": {
                            "summary": "Unsupported rate side",
                            "value": {
                                "detail": [
                                    {
                                        "type": "enum",
                                        "loc": ["query", "side"],
                                        "msg": "Input should be 'BUY' or 'SELL'",
                                        "input": "HOLD",
                                        "ctx": {"expected": "'BUY' or 'SELL'"},
                                    }
                                ]
                            },
                        },
                        "missingRateDate": {
                            "summary": "Required rate_date is missing",
                            "value": {
                                "detail": [
                                    {
                                        "type": "missing",
                                        "loc": ["query", "rate_date"],
                                        "msg": "Field required",
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
def list_rates(
    session: DbSession,
    rate_date: Annotated[
        date,
        Query(description="Date of the exchange-rate snapshot, in YYYY-MM-DD format."),
    ],
    base_currency: Annotated[
        str | None,
        Query(
            min_length=3,
            max_length=3,
            description="Base currency in the pair, for example PHP.",
        ),
    ] = None,
    target_currency: Annotated[
        str | None,
        Query(
            min_length=3,
            max_length=3,
            description="Target currency in the pair, for example USD.",
        ),
    ] = None,
    side: Annotated[
        ExchangeRateSide | None,
        Query(description="Optional rate side. Omit it to return both BUY and SELL."),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Number of matching records to skip."),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=500, description="Maximum records to return; defaults to 20."),
    ] = 20,
) -> list[ExchangeRateResponse]:
    """List exchange-rate records matching the supplied query filters."""
    return list(
        list_exchange_rates(
            session,
            rate_date=rate_date,
            base_currency=base_currency.upper() if base_currency else None,
            target_currency=target_currency.upper() if target_currency else None,
            side=side,
            offset=offset,
            limit=limit,
        )
    )


@router.get(
    "/{rate_date}/{base_currency}/{target_currency}/{side}",
    response_model=ExchangeRateResponse,
    summary="Get one exchange rate by business key",
    description=(
        "Return exactly one exchange rate identified by the complete business key: "
        "rate_date, base_currency, target_currency, and side. Unlike the collection "
        "endpoint, this resource endpoint returns one ExchangeRateResponse or 404 when "
        "no exact match exists."
    ),
    response_description="The exchange rate matching the complete business key.",
    responses={
        200: {
            "description": "The exchange rate matching the complete business key.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "0198f2b3-7c5a-7e01-8b2d-123456789abc",
                        "rate_date": "2026-09-06",
                        "base_currency": "PHP",
                        "target_currency": "USD",
                        "side": "BUY",
                        "exchange_rate": "0.0161164831",
                        "created_at": "2026-09-06T00:00:00Z",
                    }
                }
            },
        },
        404: {
            "description": "No exchange rate matches the supplied business key.",
            "content": {
                "application/json": {
                    "example": {"detail": "Exchange rate not found."}
                }
            },
        },
        422: {
            "model": ValidationErrorResponse,
            "description": "One or more path parameters are invalid.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "enum",
                                "loc": ["path", "side"],
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
def get_rate_by_key(
    session: DbSession,
    rate_date: date,
    base_currency: Annotated[
        str,
        Path(
            min_length=3,
            max_length=3,
            description="Base currency in the pair, for example PHP.",
        ),
    ],
    target_currency: Annotated[
        str,
        Path(
            min_length=3,
            max_length=3,
            description="Target currency in the pair, for example USD.",
        ),
    ],
    side: Annotated[
        ExchangeRateSide,
        Path(description="Rate side. Must be BUY or SELL."),
    ],
) -> ExchangeRateResponse:
    """Return one exchange rate by its complete business key."""
    rate = get_exchange_rate_by_key(
        session,
        rate_date=rate_date,
        base_currency=base_currency.upper(),
        target_currency=target_currency.upper(),
        side=side,
    )
    if rate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange rate not found.",
        )
    return rate


# POST endpoints
@router.post(
    "/batch",
    response_model=ExchangeRateBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create exchange rates in bulk",
    description=(
        "Create a complete rate set for one date and base currency. The rates array "
        "contains the target currency, side, and value for each rate. Each "
        "target_currency and side combination must be unique, and target_currency "
        "must differ from base_currency. This dedicated bulk operation returns the "
        "created records plus their count."
    ),
    response_description="The created exchange-rate records and their count.",
    openapi_extra=batch_create_openapi_extra(),
    responses={
        201: {
            "description": "The rate set was created successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "rates": [
                            {
                                "id": "0198f2b3-7c5a-7e01-8b2d-123456789abc",
                                "rate_date": "2026-09-06",
                                "base_currency": "PHP",
                                "target_currency": "USD",
                                "side": "BUY",
                                "exchange_rate": "0.0161164831",
                                "created_at": "2026-09-06T00:00:00Z",
                            },
                            {
                                "id": "0198f2b3-7c5a-7e02-8b2d-123456789abd",
                                "rate_date": "2026-09-06",
                                "base_currency": "PHP",
                                "target_currency": "USD",
                                "side": "SELL",
                                "exchange_rate": "0.0157973449",
                                "created_at": "2026-09-06T00:00:00Z",
                            },
                        ],
                        "count": 2,
                    }
                }
            },
        },
        409: {
            "description": "One or more rates already exist for the date and currency pair.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "One or more exchange rates already exist for this date and currency pair."
                    }
                }
            },
        },
        422: {
            "model": ValidationErrorResponse,
            "description": (
                "The request body is invalid. This includes a malformed rate_date, "
                "invalid currency code, unsupported side, non-positive exchange rate, "
                "an empty rates array, duplicate target_currency and side values, or "
                "a target_currency equal to base_currency."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "duplicateRateSide": {
                            "summary": "Duplicate target and side",
                            "value": {
                                "detail": [
                                    {
                                        "type": "value_error",
                                        "loc": ["body"],
                                        "msg": "Value error, rates must not contain duplicate target_currency and side values",
                                        "input": {
                                            "rate_date": "2026-09-06",
                                            "base_currency": "PHP",
                                            "rates": [
                                                {
                                                    "target_currency": "USD",
                                                    "side": "BUY",
                                                    "exchange_rate": "0.0161164831",
                                                },
                                                {
                                                    "target_currency": "USD",
                                                    "side": "BUY",
                                                    "exchange_rate": "0.0161164831",
                                                },
                                            ],
                                        },
                                    }
                                ]
                            },
                        },
                        "invalidExchangeRate": {
                            "summary": "Exchange rate must be positive",
                            "value": {
                                "detail": [
                                    {
                                        "type": "greater_than",
                                        "loc": ["body", "rates", 0, "exchange_rate"],
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
def create_rate_batch(
    payload: ExchangeRateBatchCreate,
    session: DbSession,
) -> ExchangeRateBatchResponse:
    """Create a daily exchange-rate set and return its records and count."""
    try:
        rates = create_exchange_rate_batch(session, payload)
    except DuplicateExchangeRateError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or more exchange rates already exist for this date and currency pair.",
        ) from None
    return ExchangeRateBatchResponse(rates=rates, count=len(rates))


# PUT endpoints
@router.put(
    "/{rate_date}/{base_currency}",
    response_model=ExchangeRateBatchResponse,
    summary="Replace a daily rate set",
    description=(
        "Replace the complete existing daily rate set identified by rate_date and "
        "base_currency. This operation does not create a new rate set; use POST "
        "/exchange-rates/batch for creation. "
        "For example, PUT /exchange-rates/2026-09-06/PHP replaces all PHP rates for "
        "that date. The request body contains the complete target currencies, sides, "
        "and values; omitted existing rates are deleted."
    ),
    openapi_extra=batch_update_openapi_extra(),
    responses={
        200: {
            "description": "The replacement daily rate set.",
            "content": {
                "application/json": {
                    "example": {
                        "rates": [],
                        "count": 2,
                    }
                }
            },
        },
        409: {
            "description": "The replacement conflicts with an existing rate.",
            "content": {
                "application/json": {
                    "example": {"detail": "The exchange-rate batch conflicts with an existing currency pair."}
                }
            },
        },
        404: {
            "description": "No daily rate set exists for the supplied date and base currency.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Exchange-rate batch not found for the supplied date and base currency."
                    }
                }
            },
        },
        422: {
            "model": ValidationErrorResponse,
            "description": "The path parameter or replacement body is invalid.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "too_short",
                                "loc": ["body", "rates"],
                                "msg": "List should have at least 1 item after validation, not 0",
                                "input": [],
                                "ctx": {"min_length": 1},
                            }
                        ]
                    }
                }
            },
        },
    },
)
def replace_rate_batch(
    rate_date: date,
    base_currency: Annotated[
        str,
        Path(min_length=3, max_length=3, description="Base currency, for example PHP."),
    ],
    payload: ExchangeRateBatchUpdate,
    session: DbSession,
) -> ExchangeRateBatchResponse:
    """Replace an existing daily exchange-rate set."""
    normalized_base_currency = base_currency.upper()
    if normalized_base_currency in {
        item.target_currency for item in payload.rates
    }:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="target_currency must differ from base_currency.",
        )
    try:
        rates = replace_exchange_rate_batch(
            session,
            rate_date,
            normalized_base_currency,
            payload,
        )
    except ExchangeRateBatchNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange-rate batch not found for the supplied date and base currency.",
        ) from None
    except DuplicateExchangeRateError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The exchange-rate batch conflicts with an existing currency pair.",
        ) from None
    return ExchangeRateBatchResponse(rates=rates, count=len(rates))


@router.put(
    "/{rate_date}/{base_currency}/{target_currency}/{side}",
    response_model=ExchangeRateResponse,
    summary="Update a rate by business key",
    description=(
        "Update only the exchange_rate value of the rate identified by the complete "
        "business key: rate_date, base_currency, target_currency, and side. The key "
        "fields are not changed by this operation. For example, PUT "
        "/exchange-rates/2026-09-06/PHP/USD/BUY with {\"exchange_rate\": \"0.0161164831\"} "
        "updates the PHP/USD BUY rate for that date."
    ),
    openapi_extra=value_update_openapi_extra(),
    responses={
        200: {
            "description": "The updated exchange rate.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "0198f2b3-7c5a-7e01-8b2d-123456789abc",
                        "rate_date": "2026-09-06",
                        "base_currency": "PHP",
                        "target_currency": "USD",
                        "side": "BUY",
                        "exchange_rate": "0.0161164831",
                        "created_at": "2026-09-06T00:00:00Z",
                    }
                }
            },
        },
        404: {
            "description": "No exchange rate matches the supplied business key.",
            "content": {
                "application/json": {
                    "example": {"detail": "Exchange rate not found."}
                }
            },
        },
        422: {
            "model": ValidationErrorResponse,
            "description": "The path parameter or exchange-rate value is invalid.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "greater_than",
                                "loc": ["body", "exchange_rate"],
                                "msg": "Input should be greater than 0",
                                "input": "0",
                                "ctx": {"gt": 0},
                            }
                        ]
                    }
                }
            },
        },
    },
)
def update_rate_by_key(
    rate_date: date,
    base_currency: Annotated[
        str,
        Path(min_length=3, max_length=3, description="Base currency, for example PHP."),
    ],
    target_currency: Annotated[
        str,
        Path(min_length=3, max_length=3, description="Target currency, for example USD."),
    ],
    side: Annotated[ExchangeRateSide, Path(description="Rate side. Must be BUY or SELL.")],
    payload: ExchangeRateValueUpdate,
    session: DbSession,
) -> ExchangeRateResponse:
    """Update one exchange-rate value by its complete business key."""
    rate = update_exchange_rate_by_key(
        session,
        rate_date=rate_date,
        base_currency=base_currency.upper(),
        target_currency=target_currency.upper(),
        side=side,
        payload=payload,
    )
    if rate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange rate not found.",
        )
    return rate


# DELETE endpoints
@router.delete(
    "/{rate_date}/{base_currency}",
    response_model=ExchangeRateBatchDeleteResponse,
    summary="Delete a daily rate set",
    description=(
        "Delete all BUY and SELL rates for the daily rate set identified by rate_date "
        "and base_currency. For example, DELETE /exchange-rates/2026-09-06/PHP "
        "removes all PHP rates for that date."
    ),
    responses={
        200: {
            "description": "The daily rate set was deleted.",
            "content": {
                "application/json": {
                    "example": {
                        "rate_date": "2026-09-06",
                        "base_currency": "PHP",
                        "deleted_count": 2,
                    }
                }
            },
        },
        422: {
            "model": ValidationErrorResponse,
            "description": (
                "The rate_date or base_currency path parameter is invalid. The base "
                "currency must be a valid ISO 4217 code."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "string_too_short",
                                "loc": ["path", "base_currency"],
                                "msg": "String should have at least 3 characters",
                                "input": "PH",
                                "ctx": {"min_length": 3},
                            }
                        ]
                    }
                }
            },
        },
    },
)
def delete_rate_batch(
    rate_date: date,
    base_currency: Annotated[
        str,
        Path(min_length=3, max_length=3, description="Base currency, for example PHP."),
    ],
    session: DbSession,
) -> ExchangeRateBatchDeleteResponse:
    """Delete a daily exchange-rate set and report the number removed."""
    try:
        normalized_base_currency = normalize_currency_code(base_currency)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    deleted_count = delete_exchange_rate_batch(
        session,
        rate_date,
        normalized_base_currency,
    )
    return ExchangeRateBatchDeleteResponse(
        rate_date=rate_date,
        base_currency=normalized_base_currency,
        deleted_count=deleted_count,
    )





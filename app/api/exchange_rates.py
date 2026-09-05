from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ExchangeRateBatchCreate,
    ExchangeRateBatchDeleteResponse,
    ExchangeRateBatchResponse,
    ExchangeRateBatchUpdate,
    ExchangeRateCreate,
    ExchangeRateResponse,
    ExchangeRateSide,
    ExchangeRateValueUpdate,
)
from app.services import (
    DuplicateExchangeRateError,
    create_exchange_rate,
    create_exchange_rate_batch,
    delete_exchange_rate,
    delete_exchange_rate_batch,
    delete_exchange_rate_by_key,
    get_exchange_rate,
    get_exchange_rate_by_key,
    list_exchange_rates,
    replace_exchange_rate_batch,
    update_exchange_rate,
    update_exchange_rate_by_key,
)

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])
DbSession = Annotated[Session, Depends(get_db)]


# GET endpoints
@router.get(
    "",
    response_model=list[ExchangeRateResponse],
    summary="List exchange rates",
    description=(
        "List exchange-rate snapshots with optional filters. This endpoint returns a "
        "collection and may return multiple rows; use GET /exchange-rates/lookup when "
        "you need the single rate identified by date, base currency, target currency, "
        "and side."
    ),
    response_description="The matching exchange-rate snapshots.",
)
def list_rates(
    session: DbSession,
    rate_date: Annotated[date | None, Query()] = None,
    base_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    target_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[ExchangeRateResponse]:
    return list(
        list_exchange_rates(
            session,
            rate_date=rate_date,
            base_currency=base_currency.upper() if base_currency else None,
            target_currency=target_currency.upper() if target_currency else None,
            offset=offset,
            limit=limit,
        )
    )


@router.get(
    "/lookup",
    response_model=ExchangeRateResponse,
    summary="Find one exchange rate by business key",
    description=(
        "Return exactly one rate for the complete business key: rate_date, "
        "base_currency, target_currency, and side. Unlike the collection endpoint, "
        "this endpoint returns one ExchangeRateResponse or 404 when no exact match exists."
    ),
    response_description="The exchange rate matching the complete business key.",
    responses={404: {"description": "No exchange rate matches the supplied key."}},
)
def get_rate_by_key(
    session: DbSession,
    rate_date: Annotated[date, Query()],
    base_currency: Annotated[str, Query(min_length=3, max_length=3)],
    target_currency: Annotated[str, Query(min_length=3, max_length=3)],
    side: ExchangeRateSide,
) -> ExchangeRateResponse:
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


@router.get(
    "/{rate_id}",
    response_model=ExchangeRateResponse,
    summary="Get an exchange rate",
    description=(
        "Retrieve one exchange-rate resource by its database UUID. Use /lookup when "
        "the business key is known instead of the resource ID."
    ),
    responses={404: {"description": "Exchange rate not found."}},
)
def get_rate(rate_id: UUID, session: DbSession) -> ExchangeRateResponse:
    rate = get_exchange_rate(session, rate_id)
    if rate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange rate not found.",
        )
    return rate


# POST endpoints
@router.post(
    "",
    response_model=ExchangeRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an exchange rate",
    description=(
        "Create one daily BUY or SELL rate. The combination of rate_date, "
        "base_currency, target_currency, and side must be unique. Use POST /batch "
        "when loading several rates for one date and base currency."
    ),
    responses={409: {"description": "A rate already exists for this date and currency pair."}},
)
def create_rate(
    payload: ExchangeRateCreate,
    session: DbSession,
) -> ExchangeRateResponse:
    try:
        return create_exchange_rate(session, payload)
    except DuplicateExchangeRateError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An exchange rate already exists for this date and currency pair.",
        ) from None


@router.post(
    "/batch",
    response_model=ExchangeRateBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create exchange rates in bulk",
    description=(
        "Create a rate set for one date and base currency. The rates array contains "
        "the target currency, side, and value for each rate. This is a dedicated bulk "
        "operation for rate ingestion and returns the created records plus their count."
    ),
    responses={409: {"description": "One or more rates already exist."}},
)
def create_rate_batch(
    payload: ExchangeRateBatchCreate,
    session: DbSession,
) -> ExchangeRateBatchResponse:
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
    "/batch/{rate_date}",
    response_model=ExchangeRateBatchResponse,
    summary="Replace a daily rate batch",
    description=(
        "Replace the complete rate set for rate_date and the base_currency supplied in "
        "the request body. Use this operation for correcting or reloading a daily "
        "ingestion set; it returns the replacement records plus their count."
    ),
    responses={409: {"description": "The replacement conflicts with an existing rate."}},
)
def replace_rate_batch(
    rate_date: date,
    payload: ExchangeRateBatchUpdate,
    session: DbSession,
) -> ExchangeRateBatchResponse:
    try:
        rates = replace_exchange_rate_batch(session, rate_date, payload)
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
        "fields are not changed by this operation."
    ),
    responses={404: {"description": "Exchange rate not found."}},
)
def update_rate_by_key(
    rate_date: date,
    base_currency: Annotated[str, Path(min_length=3, max_length=3)],
    target_currency: Annotated[str, Path(min_length=3, max_length=3)],
    side: ExchangeRateSide,
    payload: ExchangeRateValueUpdate,
    session: DbSession,
) -> ExchangeRateResponse:
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


@router.put(
    "/{rate_id}",
    response_model=ExchangeRateResponse,
    summary="Replace an exchange rate",
    description=(
        "Replace an exchange-rate resource by UUID. The request supplies the complete "
        "rate representation, including its date, currencies, side, and value."
    ),
    responses={
        404: {"description": "Exchange rate not found."},
        409: {"description": "A rate already exists for the replacement key."},
    },
)
def update_rate(
    rate_id: UUID,
    payload: ExchangeRateCreate,
    session: DbSession,
) -> ExchangeRateResponse:
    rate = get_exchange_rate(session, rate_id)
    if rate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange rate not found.",
        )
    try:
        return update_exchange_rate(session, rate, payload)
    except DuplicateExchangeRateError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An exchange rate already exists for this date and currency pair.",
        ) from None


# DELETE endpoints
@router.delete(
    "/batch/{rate_date}",
    response_model=ExchangeRateBatchDeleteResponse,
    summary="Delete a daily rate batch",
    description=(
        "Delete all BUY and SELL rates for the supplied rate_date and base_currency. "
        "The response reports the normalized base currency and number of deleted rows."
    ),
)
def delete_rate_batch(
    rate_date: date,
    base_currency: Annotated[str, Query(min_length=3, max_length=3)],
    session: DbSession,
) -> ExchangeRateBatchDeleteResponse:
    normalized_base_currency = base_currency.upper()
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


@router.delete(
    "/{rate_date}/{base_currency}/{target_currency}/{side}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a rate by business key",
    description=(
        "Delete one rate identified by its complete business key: rate_date, "
        "base_currency, target_currency, and side."
    ),
    responses={404: {"description": "Exchange rate not found."}},
)
def delete_rate_by_key(
    rate_date: date,
    base_currency: Annotated[str, Path(min_length=3, max_length=3)],
    target_currency: Annotated[str, Path(min_length=3, max_length=3)],
    side: ExchangeRateSide,
    session: DbSession,
) -> Response:
    deleted = delete_exchange_rate_by_key(
        session,
        rate_date=rate_date,
        base_currency=base_currency.upper(),
        target_currency=target_currency.upper(),
        side=side,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange rate not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{rate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an exchange rate",
    description=(
        "Delete one exchange-rate resource by UUID. This is the resource-ID equivalent "
        "of deleting by business key."
    ),
    responses={404: {"description": "Exchange rate not found."}},
)
def delete_rate(rate_id: UUID, session: DbSession) -> Response:
    rate = get_exchange_rate(session, rate_id)
    if rate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange rate not found.",
        )
    delete_exchange_rate(session, rate)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

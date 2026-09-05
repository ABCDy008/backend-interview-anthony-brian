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
    description="List daily rates, optionally filtered by date or currency pair.",
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
    summary="Look up an exchange rate",
    description="Find the BUY or SELL rate for a date, base currency, and target currency.",
    response_description="The requested exchange rate.",
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
    description="Retrieve one exchange-rate record by its UUID.",
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
    description="Create one daily BUY or SELL rate for a currency pair.",
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
    description="Create multiple rates for one date and base currency.",
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
    description="Replace the rates for one date and base currency.",
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
    description="Update the value of a rate identified by date, currencies, and side.",
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
    description="Replace an exchange-rate record by UUID.",
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
    description="Delete all rates for a date and base currency.",
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
    description="Delete one rate identified by date, currencies, and side.",
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
    description="Delete one exchange-rate record by UUID.",
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

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ExchangeRateBatchCreate,
    ExchangeRateBatchDeleteResponse,
    ExchangeRateBatchResponse,
    ExchangeRateBatchUpdate,
    ExchangeRateCreate,
    ExchangeRateResponse,
)
from app.services import (
    DuplicateExchangeRateError,
    create_exchange_rate,
    create_exchange_rate_batch,
    delete_exchange_rate,
    delete_exchange_rate_batch,
    get_exchange_rate,
    list_exchange_rates,
    replace_exchange_rate_batch,
    update_exchange_rate,
)

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=list[ExchangeRateResponse],
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


@router.post(
    "",
    response_model=ExchangeRateResponse,
    status_code=status.HTTP_201_CREATED,
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


@router.put(
    "/batch/{rate_date}",
    response_model=ExchangeRateBatchResponse,
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


@router.delete(
    "/batch/{rate_date}",
    response_model=ExchangeRateBatchDeleteResponse,
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


@router.get(
    "/{rate_id}",
    response_model=ExchangeRateResponse,
)
def get_rate(rate_id: UUID, session: DbSession) -> ExchangeRateResponse:
    rate = get_exchange_rate(session, rate_id)
    if rate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange rate not found.",
        )
    return rate


@router.put(
    "/{rate_id}",
    response_model=ExchangeRateResponse,
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


@router.delete(
    "/{rate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
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

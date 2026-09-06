from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.exchange_rates import (
    ExchangeRateBatchCreate,
    ExchangeRateCreate,
    ExchangeRateResponse,
)
from app.schemas.transactions import (
    BuyTransactionCreate,
    CrossSellTransactionCreate,
    SellTransactionCreate,
)


def operation_payload(model: type, **overrides):
    payload = {
        "transaction_timestamp": datetime(2026, 9, 5, 12, tzinfo=UTC),
        "target_currency": "USD",
        "foreign_amount": Decimal(100),
    }
    payload.update(overrides)
    return model.model_validate(payload)


def test_operation_schemas_reject_side():
    with pytest.raises(ValidationError):
        operation_payload(BuyTransactionCreate, side="BUY")

    with pytest.raises(ValidationError):
        operation_payload(SellTransactionCreate, side="SELL")

    with pytest.raises(ValidationError):
        operation_payload(BuyTransactionCreate, base_currency="PHP")


def test_currency_codes_must_be_valid_iso_4217_codes():
    with pytest.raises(ValidationError, match="valid ISO 4217"):
        ExchangeRateCreate(
            rate_date=datetime(2026, 9, 5, tzinfo=UTC).date(),
            base_currency="ZZZ",
            target_currency="USD",
            side="BUY",
            exchange_rate=Decimal("0.5"),
        )


def test_currency_codes_are_normalized_to_uppercase():
    payload = ExchangeRateCreate(
        rate_date=datetime(2026, 9, 5, tzinfo=UTC).date(),
        base_currency="php",
        target_currency="usd",
        side="BUY",
        exchange_rate=Decimal("0.5"),
    )

    assert payload.base_currency == "PHP"
    assert payload.target_currency == "USD"


def test_exchange_rate_response_accepts_persisted_legacy_currency_code():
    response = ExchangeRateResponse.model_validate(
        {
            "id": "0198f2c3-0a4b-7c8d-9e0f-123456789abc",
            "rate_date": "2026-09-05",
            "base_currency": "PHP",
            "target_currency": "ANG",
            "side": "BUY",
            "exchange_rate": "0.0287702130",
            "created_at": None,
        }
    )

    assert response.target_currency == "ANG"


def test_operation_schemas_require_exactly_one_amount():
    with pytest.raises(ValidationError, match="exactly one"):
        operation_payload(BuyTransactionCreate, foreign_amount=None)

    with pytest.raises(ValidationError, match="exactly one"):
        operation_payload(
            BuyTransactionCreate,
            foreign_amount=Decimal(100),
            base_amount=Decimal(5000),
        )


def test_cross_sell_requires_exactly_one_directional_amount():
    common = {
        "transaction_timestamp": datetime(2026, 9, 5, 12, tzinfo=UTC),
        "source_currency": "USD",
        "target_currency": "JPY",
    }
    with pytest.raises(ValidationError, match="exactly one"):
        CrossSellTransactionCreate(**common)

    with pytest.raises(ValidationError, match="exactly one"):
        CrossSellTransactionCreate(
            **common,
            source_amount=Decimal(100),
            target_amount=Decimal(15000),
        )


@pytest.mark.parametrize(
    "rates",
    [
        [
            {"target_currency": "USD", "side": "BUY", "exchange_rate": "0.5"},
            {"target_currency": "USD", "side": "BUY", "exchange_rate": "0.6"},
        ],
        [
            {"target_currency": "PHP", "side": "BUY", "exchange_rate": "0.5"},
        ],
    ],
)
def test_exchange_rate_batch_rejects_duplicate_or_base_currency_targets(rates):
    with pytest.raises(ValueError):
            ExchangeRateBatchCreate(
                rate_date=datetime(2026, 9, 5, tzinfo=UTC).date(),
                base_currency="PHP",
                rates=rates,
            )

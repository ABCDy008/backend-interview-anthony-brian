from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.schemas.exchange_rates import (
    ExchangeRateBatchCreate,
    ExchangeRateBatchUpdate,
    ExchangeRateValueUpdate,
)
from app.services.exchange_rates import (
    DuplicateExchangeRateError,
    ExchangeRateBatchNotFoundError,
    create_exchange_rate_batch,
    delete_exchange_rate_batch,
    list_exchange_rates,
    replace_exchange_rate_batch,
    update_exchange_rate_by_key,
)

RATE_DATE = date(2026, 9, 5)
TRANSACTION_TIMESTAMP = datetime(2026, 9, 5, 12, tzinfo=UTC)


def rate_batch_payload() -> ExchangeRateBatchCreate:
    return ExchangeRateBatchCreate(
        rate_date=RATE_DATE,
        base_currency="PHP",
        rates=[
            {"target_currency": "USD", "side": "BUY", "exchange_rate": "0.5"},
            {"target_currency": "USD", "side": "SELL", "exchange_rate": "0.6"},
        ],
    )


def test_list_exchange_rates_applies_filters_and_pagination():
    session = Mock()
    session.scalars.return_value.all.return_value = ["rate"]

    result = list_exchange_rates(
        session,
        rate_date=RATE_DATE,
        base_currency="PHP",
        target_currency="USD",
        side="BUY",
        offset=10,
        limit=20,
    )

    assert result == ["rate"]
    statement = session.scalars.call_args.args[0]
    params = statement.compile().params
    assert params["rate_date_1"] == RATE_DATE
    assert params["base_currency_1"] == "PHP"
    assert params["target_currency_1"] == "USD"
    assert params["side_1"] == "BUY"
    assert statement._offset == 10
    assert statement._limit == 20


def test_create_exchange_rate_batch_persists_and_refreshes_all_rates():
    session = Mock()

    result = create_exchange_rate_batch(session, rate_batch_payload())

    assert len(result) == 2
    assert [rate.target_currency for rate in result] == ["USD", "USD"]
    assert [rate.side for rate in result] == ["BUY", "SELL"]
    session.add_all.assert_called_once_with(result)
    session.commit.assert_called_once()
    assert session.refresh.call_count == 2


def test_create_exchange_rate_batch_translates_duplicate_database_error():
    session = Mock()
    session.commit.side_effect = IntegrityError("insert", {}, Exception("duplicate"))

    with pytest.raises(DuplicateExchangeRateError):
        create_exchange_rate_batch(session, rate_batch_payload())

    session.rollback.assert_called_once()


def test_replace_exchange_rate_batch_updates_adds_and_removes_rates():
    stale_rate = SimpleNamespace(target_currency="CAD", side="BUY", exchange_rate=Decimal(1))
    existing_rate = SimpleNamespace(target_currency="USD", side="BUY", exchange_rate=Decimal(1))
    session = Mock()
    session.scalars.return_value.all.return_value = [stale_rate, existing_rate]
    payload = ExchangeRateBatchUpdate(
        rates=[
            {"target_currency": "USD", "side": "BUY", "exchange_rate": "0.5"},
            {"target_currency": "JPY", "side": "SELL", "exchange_rate": "2"},
        ]
    )

    result = replace_exchange_rate_batch(session, RATE_DATE, "PHP", payload)

    assert result == [existing_rate, result[1]]
    assert existing_rate.exchange_rate == Decimal("0.5")
    assert result[1].target_currency == "JPY"
    session.delete.assert_called_once_with(stale_rate)
    session.commit.assert_called_once()


def test_replace_exchange_rate_batch_rejects_missing_snapshot():
    session = Mock()
    session.scalars.return_value.all.return_value = []

    with pytest.raises(ExchangeRateBatchNotFoundError):
        replace_exchange_rate_batch(session, RATE_DATE, "PHP", rate_batch_payload())

    session.commit.assert_not_called()


def test_delete_exchange_rate_batch_returns_deleted_count():
    session = Mock()
    session.scalars.return_value.all.return_value = ["first", "second"]

    result = delete_exchange_rate_batch(session, RATE_DATE, "PHP")

    assert result == 2
    assert session.delete.call_count == 2
    session.commit.assert_called_once()


def test_update_exchange_rate_by_key_updates_matching_rate():
    rate = SimpleNamespace(exchange_rate=Decimal("0.5"))
    session = Mock()

    with patch("app.services.exchange_rates.get_exchange_rate_by_key", return_value=rate):
        result = update_exchange_rate_by_key(
            session,
            rate_date=RATE_DATE,
            base_currency="PHP",
            target_currency="USD",
            side="BUY",
            payload=ExchangeRateValueUpdate(exchange_rate=Decimal("0.6")),
        )

    assert result is rate
    assert rate.exchange_rate == Decimal("0.6")
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(rate)


def test_update_exchange_rate_by_key_returns_none_when_missing():
    session = Mock()

    with patch("app.services.exchange_rates.get_exchange_rate_by_key", return_value=None):
        result = update_exchange_rate_by_key(
            session,
            rate_date=RATE_DATE,
            base_currency="PHP",
            target_currency="USD",
            side="BUY",
            payload=ExchangeRateValueUpdate(exchange_rate=Decimal("0.6")),
        )

    assert result is None
    session.commit.assert_not_called()


def test_replace_exchange_rate_batch_translates_duplicate_database_error():
    session = Mock()
    session.scalars.return_value.all.return_value = [
        SimpleNamespace(target_currency="USD", side="BUY", exchange_rate=Decimal("0.5"))
    ]
    session.commit.side_effect = IntegrityError("update", {}, Exception("duplicate"))

    with pytest.raises(DuplicateExchangeRateError):
        replace_exchange_rate_batch(
            session,
            RATE_DATE,
            "PHP",
            ExchangeRateBatchUpdate(
                rates=[
                    {
                        "target_currency": "USD",
                        "side": "BUY",
                        "exchange_rate": "0.6",
                    }
                ]
            ),
        )

    session.rollback.assert_called_once()



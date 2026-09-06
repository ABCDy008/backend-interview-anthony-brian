from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.schemas.transactions import (
    BuyTransactionCreate,
    CrossSellTransactionCreate,
    SellTransactionCreate,
)
from app.services.transactions import (
    InvalidTransactionOperationError,
    MissingExchangeRateError,
    _create_cross_currency_transaction,
    _create_single_leg_transaction,
    create_buy_transaction,
    create_cross_sell_transaction,
    create_sell_transaction,
    get_exchange_rate_by_key,
    list_foreign_exchange_transactions,
)

TRANSACTION_DATE = date(2026, 9, 5)
TRANSACTION_TIMESTAMP = datetime(2026, 9, 5, 12, tzinfo=UTC)


def operation_payload(model: type, **overrides):
    payload = {
        "transaction_timestamp": TRANSACTION_TIMESTAMP,
        "target_currency": "USD",
        "foreign_amount": Decimal(100),
    }
    payload.update(overrides)
    return model.model_validate(payload)


def test_rate_lookup_uses_date_currency_pair_and_side():
    session = Mock()
    expected_rate = SimpleNamespace(exchange_rate=Decimal("0.5"), side="BUY")
    session.scalar.return_value = expected_rate

    result = get_exchange_rate_by_key(
        session,
        rate_date=TRANSACTION_DATE,
        base_currency="PHP",
        target_currency="USD",
        side="BUY",
    )

    assert result is expected_rate
    statement = session.scalar.call_args.args[0]
    assert statement.compile().params == {
        "rate_date_1": TRANSACTION_DATE,
        "base_currency_1": "PHP",
        "target_currency_1": "USD",
        "side_1": "BUY",
    }


def test_rate_lookup_returns_none_when_no_rate_matches():
    session = Mock()
    session.scalar.return_value = None

    result = get_exchange_rate_by_key(
        session,
        rate_date=TRANSACTION_DATE,
        base_currency="PHP",
        target_currency="USD",
        side="SELL",
    )

    assert result is None


def test_list_transactions_filters_by_business_date_and_logical_id():
    session = Mock()
    session.scalars.return_value.all.return_value = ["transaction"]
    transaction_id = "0198f2b3-7c5a-7e01-8b2d-123456789abc"

    with patch(
        "app.services.transactions.get_settings",
        return_value=SimpleNamespace(business_timezone="UTC"),
    ):
        result = list_foreign_exchange_transactions(
            session,
            transaction_id=transaction_id,
            transaction_date=TRANSACTION_DATE,
            transaction_timestamp=TRANSACTION_TIMESTAMP,
            base_currency="PHP",
            target_currency="USD",
            side="BUY",
            offset=2,
            limit=5,
        )

    assert result == ["transaction"]
    statement = session.scalars.call_args.args[0]
    params = statement.compile().params
    assert params["transaction_id_1"] == transaction_id
    assert params["base_currency_1"] == "PHP"
    assert params["target_currency_1"] == "USD"
    assert params["side_1"] == "BUY"
    assert params["transaction_timestamp_1"].date() == TRANSACTION_DATE
    assert TRANSACTION_TIMESTAMP in params.values()
    assert statement._offset == 2
    assert statement._limit == 5


@pytest.mark.parametrize(
    ("payload_type", "side", "expected_fee"),
    [
        (BuyTransactionCreate, "BUY", Decimal("1.00")),
        (SellTransactionCreate, "SELL", Decimal("0.50")),
    ],
)
def test_single_leg_calculation_persists_rate_snapshot_and_fee(
    payload_type,
    side,
    expected_fee,
):
    session = Mock()
    rate = SimpleNamespace(side=side, exchange_rate=Decimal("0.5"))
    payload = operation_payload(payload_type).model_copy(
        update={"base_currency": "PHP", "side": side}
    )

    with patch("app.services.transactions.get_exchange_rate_by_key", return_value=rate):
        transaction = _create_single_leg_transaction(session, payload)

    assert transaction.effective_rate == Decimal("0.5")
    assert transaction.fee == expected_fee
    session.commit.assert_called_once()


def test_single_leg_creation_raises_when_rate_is_missing():
    session = Mock()
    payload = SimpleNamespace(
        transaction_timestamp=TRANSACTION_TIMESTAMP,
        base_currency="PHP",
        target_currency="USD",
        side="BUY",
        foreign_amount=Decimal(100),
        base_amount=None,
    )

    with (
        patch("app.services.transactions.get_exchange_rate_by_key", return_value=None),
        pytest.raises(MissingExchangeRateError),
    ):
        _create_single_leg_transaction(session, payload)

    session.commit.assert_not_called()


def test_buy_and_sell_operations_select_home_currency_and_side():
    transaction = Mock()
    for operation, payload_type, expected_side in (
        (create_buy_transaction, BuyTransactionCreate, "BUY"),
        (create_sell_transaction, SellTransactionCreate, "SELL"),
    ):
        with (
            patch("app.services.transactions.get_settings", return_value=SimpleNamespace(home_currency="PHP")),
            patch("app.services.transactions._create_single_leg_transaction", return_value=transaction) as create,
        ):
            result = operation(Mock(), operation_payload(payload_type))

        assert result == [transaction]
        assert create.call_args.args[1].base_currency == "PHP"
        assert create.call_args.args[1].side == expected_side


def test_buy_and_sell_operations_accept_base_amount():
    transaction = Mock()
    for operation, payload_type in (
        (create_buy_transaction, BuyTransactionCreate),
        (create_sell_transaction, SellTransactionCreate),
    ):
        with (
            patch("app.services.transactions.get_settings", return_value=SimpleNamespace(home_currency="PHP")),
            patch("app.services.transactions._create_single_leg_transaction", return_value=transaction) as create,
        ):
            result = operation(
                Mock(),
                operation_payload(
                    payload_type,
                    foreign_amount=None,
                    base_amount=Decimal(5000),
                ),
            )

        assert result == [transaction]
        internal_payload = create.call_args.args[1]
        assert internal_payload.foreign_amount is None
        assert internal_payload.base_amount == Decimal(5000)


@pytest.mark.parametrize("operation", [create_buy_transaction, create_sell_transaction])
def test_normal_operation_rejects_home_currency_target(operation):
    payload_type = BuyTransactionCreate if operation is create_buy_transaction else SellTransactionCreate
    payload = operation_payload(payload_type, target_currency="PHP")

    with (
        patch("app.services.transactions.get_settings", return_value=SimpleNamespace(home_currency="PHP")),
        pytest.raises(InvalidTransactionOperationError, match="target_currency"),
    ):
        operation(Mock(), payload)


def test_cross_sell_selects_non_home_currencies_and_internal_legs():
    buy_leg = Mock()
    sell_leg = Mock()
    with (
        patch("app.services.transactions.get_settings", return_value=SimpleNamespace(home_currency="PHP")),
        patch("app.services.transactions._create_cross_currency_transaction", return_value=[buy_leg, sell_leg]) as create,
    ):
        payload = CrossSellTransactionCreate(
            transaction_timestamp=TRANSACTION_TIMESTAMP,
            source_currency="USD",
            target_currency="JPY",
            source_amount=Decimal(100),
        )
        result = create_cross_sell_transaction(Mock(), payload)

    assert result == [buy_leg, sell_leg]
    assert create.call_args.kwargs["source_currency"] == "USD"
    assert create.call_args.kwargs["target_currency"] == "JPY"
    assert create.call_args.kwargs["source_amount"] == Decimal(100)


def test_cross_sell_accepts_target_amount():
    buy_leg = Mock()
    sell_leg = Mock()
    with (
        patch("app.services.transactions.get_settings", return_value=SimpleNamespace(home_currency="PHP")),
        patch("app.services.transactions._create_cross_currency_transaction", return_value=[buy_leg, sell_leg]) as create,
    ):
        payload = CrossSellTransactionCreate(
            transaction_timestamp=TRANSACTION_TIMESTAMP,
            source_currency="USD",
            target_currency="JPY",
            target_amount=Decimal(15000),
        )
        result = create_cross_sell_transaction(Mock(), payload)

    assert result == [buy_leg, sell_leg]
    assert create.call_args.kwargs["source_amount"] is None
    assert create.call_args.kwargs["target_amount"] == Decimal(15000)


def test_cross_sell_rejects_the_home_currency():
    payload = CrossSellTransactionCreate(
        transaction_timestamp=TRANSACTION_TIMESTAMP,
        source_currency="PHP",
        target_currency="USD",
        source_amount=Decimal(100),
    )

    with (
        patch("app.services.transactions.get_settings", return_value=SimpleNamespace(home_currency="PHP")),
        pytest.raises(InvalidTransactionOperationError, match="non-home currencies"),
    ):
        create_cross_sell_transaction(Mock(), payload)


def test_cross_currency_creation_links_two_legs_for_source_amount():
    session = Mock()
    buy_rate = SimpleNamespace(side="BUY", exchange_rate=Decimal("0.5"))
    sell_rate = SimpleNamespace(side="SELL", exchange_rate=Decimal(2))

    with patch(
        "app.services.transactions.get_exchange_rate_by_key",
        side_effect=[buy_rate, sell_rate],
    ):
        legs = _create_cross_currency_transaction(
            session,
            transaction_timestamp=TRANSACTION_TIMESTAMP,
            source_currency="USD",
            target_currency="JPY",
            home_currency="PHP",
            source_amount=Decimal(100),
        )

    buy_leg, sell_leg = legs
    assert buy_leg.transaction_id == sell_leg.transaction_id
    assert (buy_leg.side, buy_leg.target_currency) == ("BUY", "USD")
    assert (sell_leg.side, sell_leg.target_currency) == ("SELL", "JPY")
    assert buy_leg.foreign_amount == Decimal(100)
    assert sell_leg.base_amount == Decimal("199.00")
    session.add_all.assert_called_once_with(legs)
    session.commit.assert_called_once()


def test_cross_currency_creation_supports_target_amount():
    session = Mock()
    buy_rate = SimpleNamespace(side="BUY", exchange_rate=Decimal("0.5"))
    sell_rate = SimpleNamespace(side="SELL", exchange_rate=Decimal(2))

    with patch(
        "app.services.transactions.get_exchange_rate_by_key",
        side_effect=[buy_rate, sell_rate],
    ):
        legs = _create_cross_currency_transaction(
            session,
            transaction_timestamp=TRANSACTION_TIMESTAMP,
            source_currency="USD",
            target_currency="JPY",
            home_currency="PHP",
            target_amount=Decimal(400),
        )

    assert legs[1].foreign_amount == Decimal("400.00")
    assert legs[0].base_amount == Decimal("200.50")


def test_cross_currency_creation_requires_both_rates():
    session = Mock()
    buy_rate = SimpleNamespace(side="BUY", exchange_rate=Decimal("0.5"))

    with (
        patch(
            "app.services.transactions.get_exchange_rate_by_key",
            side_effect=[buy_rate, None],
        ),
        pytest.raises(MissingExchangeRateError),
    ):
        _create_cross_currency_transaction(
            session,
            transaction_timestamp=TRANSACTION_TIMESTAMP,
            source_currency="USD",
            target_currency="JPY",
            home_currency="PHP",
            source_amount=Decimal(100),
        )

    session.commit.assert_not_called()

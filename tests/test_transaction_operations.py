from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from app.domain import BuyCalculation, InsufficientAmountError, SellCalculation
from app.schemas import (
    BuyTransactionCreate,
    CrossSellTransactionCreate,
    ExchangeRateCreate,
    SellTransactionCreate,
)
from app.services import (
    InvalidTransactionOperationError,
    _create_single_leg_transaction,
    create_buy_transaction,
    create_cross_sell_transaction,
    create_sell_transaction,
    get_exchange_rate_by_key,
)


def operation_payload(model: type, **overrides):
    payload = {
        "transaction_timestamp": datetime(2026, 9, 5, 12, tzinfo=UTC),
        "target_currency": "USD",
        "foreign_amount": Decimal(100),
    }
    payload.update(overrides)
    return model.model_validate(payload)


def test_rate_lookup_uses_date_currency_pair_and_side():
    session = Mock()
    expected_rate = SimpleNamespace(exchange_rate=Decimal("0.5"), side="BUY")
    session.scalar.return_value = expected_rate
    rate_date = datetime(2026, 9, 5, tzinfo=UTC).date()

    result = get_exchange_rate_by_key(
        session,
        rate_date=rate_date,
        base_currency="PHP",
        target_currency="USD",
        side="BUY",
    )

    assert result is expected_rate
    statement = session.scalar.call_args.args[0]
    assert statement.compile().params == {
        "rate_date_1": rate_date,
        "base_currency_1": "PHP",
        "target_currency_1": "USD",
        "side_1": "BUY",
    }


def test_rate_lookup_returns_none_when_no_rate_matches():
    session = Mock()
    session.scalar.return_value = None

    result = get_exchange_rate_by_key(
        session,
        rate_date=datetime(2026, 9, 5, tzinfo=UTC).date(),
        base_currency="PHP",
        target_currency="USD",
        side="SELL",
    )

    assert result is None


@pytest.mark.parametrize(
    ("side", "expected_fee"),
    [("BUY", Decimal("1.00")), ("SELL", Decimal("0.50"))],
)
def test_single_leg_calculation_persists_rate_snapshot_and_fee(side, expected_fee):
    session = Mock()
    rate = SimpleNamespace(
        side=side,
        exchange_rate=Decimal("0.5"),
    )
    payload = operation_payload(
        BuyTransactionCreate if side == "BUY" else SellTransactionCreate,
        foreign_amount=Decimal(100),
    )
    payload = payload.model_copy(
        update={
            "base_currency": "PHP",
            "side": side,
        }
    )

    with patch("app.services.get_exchange_rate_by_key", return_value=rate):
        transaction = _create_single_leg_transaction(session, payload)

    assert transaction.effective_rate == Decimal("0.5")
    assert transaction.fee == expected_fee
    session.commit.assert_called_once()


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


@pytest.mark.parametrize(
    ("calculator", "expected_base"),
    [(BuyCalculation, Decimal("0.00")), (SellCalculation, Decimal("1.50"))],
)
def test_buy_and_sell_use_round_half_to_even(calculator, expected_base):
    result = calculator(Decimal(1)).calculate(
        foreign_amount=Decimal("1.005"),
        base_amount=None,
    )

    assert result.foreign_amount == Decimal("1.00")
    assert result.base_amount == expected_base


@pytest.mark.parametrize(
    ("calculator", "expected_base"),
    [(BuyCalculation, Decimal("1.02")), (SellCalculation, Decimal("2.52"))],
)
def test_round_half_to_even_rounds_toward_the_even_cent(calculator, expected_base):
    result = calculator(Decimal(1)).calculate(
        foreign_amount=Decimal("2.015"),
        base_amount=None,
    )

    assert result.foreign_amount == Decimal("2.02")
    assert result.base_amount == expected_base


def test_buy_can_preserve_intermediate_amount_precision():
    result = BuyCalculation(Decimal(3)).calculate(
        foreign_amount=Decimal(4),
        base_amount=None,
        round_foreign=False,
        round_base=False,
    )

    assert result.foreign_amount == Decimal(4)
    assert result.base_amount > Decimal("0.33")
    assert result.base_amount < Decimal("0.34")
    assert result.base_amount.as_tuple().exponent < -2
    assert result.rounding_adjustment == Decimal(0)


def test_sell_rounds_by_default():
    result = SellCalculation(Decimal(1)).calculate(
        foreign_amount=Decimal("1.005"),
        base_amount=None,
    )

    assert result.foreign_amount == Decimal("1.00")
    assert result.base_amount == Decimal("1.50")
    assert result.rounding_adjustment == Decimal("-0.005")


def test_buy_stores_signed_rounding_adjustment_for_derived_base_amount():
    result = BuyCalculation(Decimal(1)).calculate(
        foreign_amount=Decimal("2.005"),
        base_amount=None,
    )

    assert result.rounding_adjustment == Decimal("-0.005")


def test_calculations_store_operation_specific_fees():
    buy = BuyCalculation(Decimal(1)).calculate(
        foreign_amount=Decimal(2),
        base_amount=None,
    )
    sell = SellCalculation(Decimal(1)).calculate(
        foreign_amount=Decimal(2),
        base_amount=None,
    )

    assert buy.fee_amount == Decimal("1.00")
    assert sell.fee_amount == Decimal("0.50")


@pytest.mark.parametrize(
    ("calculator", "amount"),
    [(BuyCalculation, Decimal("1.00")), (SellCalculation, Decimal("0.50"))],
)
def test_base_amount_must_cover_operation_fee(calculator, amount):
    with pytest.raises(InsufficientAmountError):
        calculator(Decimal(1)).calculate(
            foreign_amount=None,
            base_amount=amount,
        )


def test_buy_stores_positive_signed_rounding_adjustment():
    result = BuyCalculation(Decimal(1)).calculate(
        foreign_amount=Decimal("1.015"),
        base_amount=None,
    )

    assert result.rounding_adjustment == Decimal("0.005")


def test_operation_schemas_require_exactly_one_amount():
    with pytest.raises(ValidationError, match="exactly one"):
        operation_payload(BuyTransactionCreate, foreign_amount=None)

    with pytest.raises(ValidationError, match="exactly one"):
        operation_payload(
            BuyTransactionCreate,
            foreign_amount=Decimal(100),
            base_amount=Decimal(5000),
        )


def test_buy_operation_accepts_base_amount_limit():
    transaction = Mock()
    with patch("app.services.get_settings", return_value=SimpleNamespace(home_currency="PHP")), \
         patch("app.services._create_single_leg_transaction", return_value=transaction) as create:
        result = create_buy_transaction(
            Mock(),
            operation_payload(
                BuyTransactionCreate,
                foreign_amount=None,
                base_amount=Decimal(5000),
            ),
        )

    assert result == [transaction]
    internal_payload = create.call_args.args[1]
    assert internal_payload.foreign_amount is None
    assert internal_payload.base_amount == Decimal(5000)


def test_sell_operation_accepts_base_amount_limit():
    transaction = Mock()
    with patch("app.services.get_settings", return_value=SimpleNamespace(home_currency="PHP")), \
         patch("app.services._create_single_leg_transaction", return_value=transaction) as create:
        result = create_sell_transaction(
            Mock(),
            operation_payload(
                SellTransactionCreate,
                foreign_amount=None,
                base_amount=Decimal(5000),
            ),
        )

    assert result == [transaction]
    internal_payload = create.call_args.args[1]
    assert internal_payload.foreign_amount is None
    assert internal_payload.base_amount == Decimal(5000)


def test_buy_operation_selects_buy_side():
    transaction = Mock()
    with patch("app.services.get_settings", return_value=SimpleNamespace(home_currency="PHP")), \
         patch("app.services._create_single_leg_transaction", return_value=transaction) as create:
        result = create_buy_transaction(Mock(), operation_payload(BuyTransactionCreate))

    assert result == [transaction]
    assert create.call_args.args[1].base_currency == "PHP"
    assert create.call_args.args[1].side == "BUY"


def test_sell_operation_selects_sell_side():
    transaction = Mock()
    with patch("app.services.get_settings", return_value=SimpleNamespace(home_currency="PHP")), \
         patch("app.services._create_single_leg_transaction", return_value=transaction) as create:
        result = create_sell_transaction(Mock(), operation_payload(SellTransactionCreate))

    assert result == [transaction]
    assert create.call_args.args[1].base_currency == "PHP"
    assert create.call_args.args[1].side == "SELL"


@pytest.mark.parametrize("operation", [create_buy_transaction, create_sell_transaction])
def test_normal_operation_rejects_home_currency_target(operation):
    payload_type = BuyTransactionCreate if operation is create_buy_transaction else SellTransactionCreate
    payload = operation_payload(payload_type, target_currency="PHP")

    with (
        patch("app.services.get_settings", return_value=SimpleNamespace(home_currency="PHP")),
        pytest.raises(InvalidTransactionOperationError, match="target_currency"),
    ):
        operation(Mock(), payload)


def test_cross_sell_selects_non_home_currencies_and_internal_legs():
    buy_leg = Mock()
    sell_leg = Mock()
    with patch("app.services.get_settings", return_value=SimpleNamespace(home_currency="PHP")), \
         patch("app.services._create_cross_currency_transaction", return_value=[buy_leg, sell_leg]) as create:
        payload = CrossSellTransactionCreate(
            transaction_timestamp=datetime(2026, 9, 5, 12, tzinfo=UTC),
            source_currency="USD",
            target_currency="JPY",
            source_amount=Decimal(100),
        )
        result = create_cross_sell_transaction(Mock(), payload)

    assert result == [buy_leg, sell_leg]
    assert create.call_args.kwargs["source_currency"] == "USD"
    assert create.call_args.kwargs["target_currency"] == "JPY"
    assert create.call_args.kwargs["source_amount"] == Decimal(100)


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


def test_cross_sell_accepts_target_amount():
    buy_leg = Mock()
    sell_leg = Mock()
    with patch("app.services.get_settings", return_value=SimpleNamespace(home_currency="PHP")), \
         patch("app.services._create_cross_currency_transaction", return_value=[buy_leg, sell_leg]) as create:
        payload = CrossSellTransactionCreate(
            transaction_timestamp=datetime(2026, 9, 5, 12, tzinfo=UTC),
            source_currency="USD",
            target_currency="JPY",
            target_amount=Decimal(15000),
        )
        result = create_cross_sell_transaction(Mock(), payload)

    assert result == [buy_leg, sell_leg]
    assert create.call_args.kwargs["source_amount"] is None
    assert create.call_args.kwargs["target_amount"] == Decimal(15000)
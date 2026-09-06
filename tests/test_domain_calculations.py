from decimal import Decimal

import pytest

from app.domain import BuyCalculation, InsufficientAmountError, SellCalculation


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
def test_round_half_even_rounds_toward_the_even_cent(calculator, expected_base):
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

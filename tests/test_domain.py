from decimal import Decimal

from app.domain import BuyCalculation, SellCalculation


def test_buy_calculation_converts_foreign_to_base():
    result = BuyCalculation(Decimal("55.00")).calculate(
        foreign_amount=Decimal("100.00"), base_amount=None
    )
    assert result.base_amount == Decimal("5500.00")


def test_sell_calculation_converts_base_to_foreign():
    result = SellCalculation(Decimal("55.00")).calculate(
        foreign_amount=None, base_amount=Decimal("5500.00")
    )
    assert result.foreign_amount == Decimal("100.00")

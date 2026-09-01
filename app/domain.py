from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Calculation:
    foreign_amount: Decimal
    base_amount: Decimal
    fee_amount: Decimal = Decimal("0.00")
    rounding_adjustment: Decimal = Decimal("0.00")


class ExchangeCalculation:
    def __init__(self, rate: Decimal):
        self.rate = rate

    def calculate(
        self, *, foreign_amount: Decimal | None, base_amount: Decimal | None
    ) -> Calculation:
        raise NotImplementedError

    @staticmethod
    def money(value: Decimal) -> Decimal:
        return value.quantize(CENT, rounding=ROUND_HALF_UP)


class BuyCalculation(ExchangeCalculation):
    """The store buys foreign currency and pays the customer in base currency."""

    def calculate(
        self, *, foreign_amount: Decimal | None, base_amount: Decimal | None
    ) -> Calculation:
        foreign = foreign_amount or (base_amount / self.rate)
        base = base_amount or (foreign * self.rate)
        return Calculation(self.money(foreign), self.money(base))


class SellCalculation(ExchangeCalculation):
    """The store sells foreign currency and receives base currency."""

    def calculate(
        self, *, foreign_amount: Decimal | None, base_amount: Decimal | None
    ) -> Calculation:
        foreign = foreign_amount or (base_amount / self.rate)
        base = base_amount or (foreign * self.rate)
        return Calculation(self.money(foreign), self.money(base))


def calculator_for(side: str, rate: Decimal) -> ExchangeCalculation:
    return BuyCalculation(rate) if side == "BUY" else SellCalculation(rate)

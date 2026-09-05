from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

CENT = Decimal("0.01")
BUY_FEE = Decimal("1.00")
SELL_FEE = Decimal("0.50")


class InsufficientAmountError(ValueError):
    pass


@dataclass(frozen=True)
class Calculation:
    foreign_amount: Decimal
    base_amount: Decimal
    fee_amount: Decimal = Decimal("0.00")
    rounding_adjustment: Decimal = Decimal("0.00")


class ExchangeCalculation:
    def __init__(self, rate: Decimal, fee: Decimal):
        self.rate = rate
        self.fee = fee

    def calculate(
        self,
        *,
        foreign_amount: Decimal | None,
        base_amount: Decimal | None,
        round_foreign: bool = True,
        round_base: bool = True,
    ) -> Calculation:
        raise NotImplementedError

    @staticmethod
    def money(value: Decimal) -> Decimal:
        return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


class BuyCalculation(ExchangeCalculation):
    """The store buys foreign currency and pays the customer in base currency."""

    def __init__(self, rate: Decimal):
        super().__init__(rate, BUY_FEE)

    def calculate(
        self,
        *,
        foreign_amount: Decimal | None,
        base_amount: Decimal | None,
        round_foreign: bool = True,
        round_base: bool = True,
    ) -> Calculation:
        if foreign_amount is not None:
            foreign = foreign_amount
            base = foreign / self.rate - self.fee
        else:
            if base_amount <= self.fee:
                raise InsufficientAmountError("base_amount must exceed the buy fee")
            base = base_amount
            foreign = (base - self.fee) * self.rate
        rounded_foreign = self.money(foreign) if round_foreign else foreign
        rounded_base = self.money(base) if round_base else base
        adjustment = (
            rounded_foreign - foreign if foreign_amount is None else rounded_base - base
        )
        return Calculation(
            rounded_foreign,
            rounded_base,
            fee_amount=self.fee,
            rounding_adjustment=adjustment,
        )


class SellCalculation(ExchangeCalculation):
    """The store sells foreign currency and receives base currency."""

    def __init__(self, rate: Decimal):
        super().__init__(rate, SELL_FEE)

    def calculate(
        self,
        *,
        foreign_amount: Decimal | None,
        base_amount: Decimal | None,
    ) -> Calculation:
        if foreign_amount is not None:
            foreign = foreign_amount
            base = foreign / self.rate + self.fee
        else:
            if base_amount <= self.fee:
                raise InsufficientAmountError("base_amount must exceed the sell fee")
            base = base_amount
            foreign = (base - self.fee) * self.rate
        rounded_foreign = self.money(foreign)
        rounded_base = self.money(base)
        adjustment = (
            rounded_foreign - foreign if foreign_amount is None else rounded_base - base
        )
        return Calculation(
            rounded_foreign,
            rounded_base,
            fee_amount=self.fee,
            rounding_adjustment=adjustment,
        )


def calculator_for(side: str, rate: Decimal) -> ExchangeCalculation:
    return BuyCalculation(rate) if side == "BUY" else SellCalculation(rate)

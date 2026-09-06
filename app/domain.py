from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

CENT = Decimal("0.01")
BUY_FEE = Decimal("1.00")
SELL_FEE = Decimal("0.50")


class InsufficientAmountError(ValueError):
    """Raised when an amount cannot cover the applicable transaction fee."""


@dataclass(frozen=True)
class Calculation:
    """Store the calculated amounts, fee, and rounding adjustment for a transaction."""

    foreign_amount: Decimal
    base_amount: Decimal
    fee_amount: Decimal = Decimal("0.00")
    rounding_adjustment: Decimal = Decimal("0.00")


class ExchangeCalculation:
    """Define the interface and shared money rounding for exchange calculations."""

    def __init__(self, rate: Decimal, fee: Decimal):
        """Initialize a calculation with an exchange rate and transaction fee."""
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
        """Calculate normalized foreign and base amounts for a transaction."""
        raise NotImplementedError

    @staticmethod
    def money(value: Decimal) -> Decimal:
        """Round a decimal amount to cents using banker’s rounding."""
        return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


class BuyCalculation(ExchangeCalculation):
    """The store buys foreign currency and pays the customer in base currency."""

    def __init__(self, rate: Decimal):
        """Initialize a buy calculation with the fixed buy fee."""
        super().__init__(rate, BUY_FEE)

    def calculate(
        self,
        *,
        foreign_amount: Decimal | None,
        base_amount: Decimal | None,
        round_foreign: bool = True,
        round_base: bool = True,
    ) -> Calculation:
        """Calculate the base or foreign amount for a store purchase."""
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
        """Initialize a sell calculation with the fixed sell fee."""
        super().__init__(rate, SELL_FEE)

    def calculate(
        self,
        *,
        foreign_amount: Decimal | None,
        base_amount: Decimal | None,
    ) -> Calculation:
        """Calculate the base or foreign amount for a store sale."""
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
    """Return the calculation strategy for a BUY or SELL operation."""
    return BuyCalculation(rate) if side == "BUY" else SellCalculation(rate)

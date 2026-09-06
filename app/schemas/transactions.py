from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.exchange_rates import ExchangeRateSide, normalize_currency_code


class ForeignExchangeTransactionFields(BaseModel):
    """Define the shared fields for persisted transaction legs."""

    transaction_id: UUID | None = Field(
        default=None,
        description="Identifier shared by the legs of one logical transaction.",
    )
    transaction_timestamp: datetime = Field(
        description="Timestamp supplied for the transaction and rate selection.",
    )
    base_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
        description="Store or home currency used as the rate base.",
    )
    target_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
        description="Foreign currency represented by this transaction leg.",
    )
    side: ExchangeRateSide = Field(description="BUY or SELL operation applied to this transaction leg.")
    effective_rate: Decimal = Field(
        gt=0, max_digits=20, decimal_places=10,
        description="Exchange rate snapshot used for this transaction leg.",
    )
    foreign_amount: Decimal = Field(
        gt=0, max_digits=20, decimal_places=10,
        description="Final amount in target_currency after calculation.",
    )
    base_amount: Decimal = Field(
        gt=0, max_digits=20, decimal_places=10,
        description="Final amount in base_currency after calculation.",
    )
    rounding_adjustment: Decimal | None = Field(
        default=None, max_digits=20, decimal_places=10,
        description="Signed adjustment produced by currency rounding, when applicable.",
    )
    fee: Decimal | None = Field(
        default=None, ge=0, max_digits=20, decimal_places=10,
        description="Fee applied to this transaction leg, when applicable.",
    )

    @model_validator(mode="after")
    def validate_currency_pair(self):
        """Reject transaction legs whose base and target currencies match."""
        if self.base_currency == self.target_currency:
            raise ValueError("base_currency and target_currency must differ")
        return self


class ForeignExchangeTransactionCreate(BaseModel):
    """Validate the internal payload used to persist a transaction leg."""

    transaction_id: UUID | None = None
    transaction_timestamp: datetime
    base_currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    target_currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    side: ExchangeRateSide
    foreign_amount: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=10)
    base_amount: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=10)

    @field_validator("base_currency", "target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize currencies in the internal transaction payload."""
        return normalize_currency_code(value)

    @model_validator(mode="after")
    def validate_create_amounts(self):
        """Require exactly one amount and distinct currencies."""
        if (self.foreign_amount is None) == (self.base_amount is None):
            raise ValueError("provide exactly one of foreign_amount or base_amount")
        if self.base_currency == self.target_currency:
            raise ValueError("base_currency and target_currency must differ")
        return self


class TransactionOperationFields(BaseModel):
    """Define shared input fields for BUY and SELL operations."""

    model_config = ConfigDict(extra="forbid")

    transaction_timestamp: datetime = Field(description="Timestamp used to select the applicable daily exchange rate.")
    target_currency: str = Field(
        min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$",
        description="Foreign currency involved in the transaction.",
    )
    foreign_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=20, decimal_places=10,
        description="Amount of target_currency to buy or sell. Provide exactly one amount field.",
    )
    base_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=20, decimal_places=10,
        description="Amount in the store's home currency. Provide exactly one amount field.",
    )

    @field_validator("target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize the operation target currency."""
        return normalize_currency_code(value)

    @model_validator(mode="after")
    def validate_amounts(self):
        """Require exactly one of foreign amount or base amount."""
        if (self.foreign_amount is None) == (self.base_amount is None):
            raise ValueError("provide exactly one of foreign_amount or base_amount")
        return self


class BuyTransactionCreate(TransactionOperationFields):
    """Represent a BUY transaction request."""


class SellTransactionCreate(TransactionOperationFields):
    """Represent a SELL transaction request."""


class CrossSellTransactionCreate(BaseModel):
    """Validate a transaction exchanging one foreign currency for another."""

    model_config = ConfigDict(extra="forbid")

    transaction_timestamp: datetime = Field(description="Timestamp used to select both daily exchange rates.")
    source_currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    target_currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    source_amount: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=10)
    target_amount: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=10)

    @field_validator("source_currency", "target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize both currencies in the cross-sell request."""
        return normalize_currency_code(value)

    @model_validator(mode="after")
    def validate_currency_pair(self):
        """Reject cross-sell requests using the same source and target currency."""
        if self.source_currency == self.target_currency:
            raise ValueError("source_currency and target_currency must differ")
        return self

    @model_validator(mode="after")
    def validate_amounts(self):
        """Require exactly one of source amount or target amount."""
        if (self.source_amount is None) == (self.target_amount is None):
            raise ValueError("provide exactly one of source_amount or target_amount")
        return self


class ForeignExchangeTransactionResponse(ForeignExchangeTransactionFields):
    """Represent a persisted transaction leg returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Unique identifier for this persisted transaction leg.")
    transaction_id: UUID = Field(description="Identifier shared by both legs of a cross-sell transaction.")
    created_at: datetime | None = Field(description="Timestamp when this transaction leg was persisted.")

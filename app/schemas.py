from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

import pycountry
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExchangeRateSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


def normalize_currency_code(value: str) -> str:
    currency_code = value.upper()
    if pycountry.currencies.get(alpha_3=currency_code) is None:
        raise ValueError("currency code must be a valid ISO 4217 code")
    return currency_code


class ExchangeRateFields(BaseModel):
    rate_date: date = Field(description="Calendar date on which this rate is effective.")
    base_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
        description="Currency held by the store and used as the rate base.",
    )
    target_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
        description="Foreign currency quoted by the rate.",
    )
    side: ExchangeRateSide = Field(
        description="BUY when the store acquires target currency; SELL when it provides target currency."
    )
    exchange_rate: Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
        description="Number of base-currency units per one target-currency unit.",
    )

    @field_validator("base_currency", "target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return normalize_currency_code(value)


class ExchangeRateCreate(ExchangeRateFields):
    pass


class ExchangeRateValueUpdate(BaseModel):
    exchange_rate: Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
    )


class ExchangeRateBatchItem(BaseModel):
    target_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    )
    exchange_rate: Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
    )
    side: ExchangeRateSide

    @field_validator("target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return normalize_currency_code(value)


class ExchangeRateBatchCreate(BaseModel):
    rate_date: date
    base_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    )
    rates: list[ExchangeRateBatchItem] = Field(min_length=1, max_length=500)

    @field_validator("base_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return normalize_currency_code(value)

    @model_validator(mode="after")
    def validate_unique_targets(self):
        pairs = [(item.target_currency, item.side) for item in self.rates]
        if len(pairs) != len(set(pairs)):
            raise ValueError("rates must not contain duplicate target_currency and side values")
        if self.base_currency in {item.target_currency for item in self.rates}:
            raise ValueError("target_currency must differ from base_currency")
        return self


class ExchangeRateBatchUpdate(BaseModel):
    base_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    )
    rates: list[ExchangeRateBatchItem] = Field(min_length=1, max_length=500)

    @field_validator("base_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return normalize_currency_code(value)

    @model_validator(mode="after")
    def validate_unique_targets(self):
        pairs = [(item.target_currency, item.side) for item in self.rates]
        if len(pairs) != len(set(pairs)):
            raise ValueError("rates must not contain duplicate target_currency and side values")
        if self.base_currency in {item.target_currency for item in self.rates}:
            raise ValueError("target_currency must differ from base_currency")
        return self


class ExchangeRateResponse(ExchangeRateFields):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime | None


class ExchangeRateBatchResponse(BaseModel):
    rates: list[ExchangeRateResponse] = Field(description="The exchange-rate records in the batch.")
    count: int = Field(description="Number of records in rates.")


class ExchangeRateBatchDeleteResponse(BaseModel):
    rate_date: date = Field(description="Date whose rates were deleted.")
    base_currency: str = Field(description="Base currency whose daily rates were deleted.")
    deleted_count: int = Field(description="Number of rate records deleted.")


class ForeignExchangeTransactionFields(BaseModel):
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
    side: ExchangeRateSide = Field(
        description="BUY or SELL operation applied to this transaction leg.",
    )
    effective_rate: Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
        description="Exchange rate snapshot used for this transaction leg.",
    )
    foreign_amount: Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
        description="Final amount in target_currency after calculation.",
    )
    base_amount: Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
        description="Final amount in base_currency after calculation.",
    )
    rounding_adjustment: Decimal | None = Field(
        default=None,
        max_digits=20,
        decimal_places=10,
        description="Signed adjustment produced by currency rounding, when applicable.",
    )
    fee: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=20,
        decimal_places=10,
        description="Fee applied to this transaction leg, when applicable.",
    )

    @field_validator("base_currency", "target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return normalize_currency_code(value)

    @model_validator(mode="after")
    def validate_currency_pair(self):
        if self.base_currency == self.target_currency:
            raise ValueError("base_currency and target_currency must differ")
        return self


class ForeignExchangeTransactionCreate(BaseModel):
    transaction_id: UUID | None = None
    transaction_timestamp: datetime
    base_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    )
    target_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    )
    side: ExchangeRateSide
    foreign_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=20,
        decimal_places=10,
    )
    base_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=20,
        decimal_places=10,
    )

    @field_validator("base_currency", "target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return normalize_currency_code(value)

    @model_validator(mode="after")
    def validate_create_amounts(self):
        if (self.foreign_amount is None) == (self.base_amount is None):
            raise ValueError("provide exactly one of foreign_amount or base_amount")
        if self.base_currency == self.target_currency:
            raise ValueError("base_currency and target_currency must differ")
        return self


class TransactionOperationFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: UUID | None = Field(
        default=None,
        description="Optional client-supplied grouping ID; generated when omitted.",
    )
    transaction_timestamp: datetime = Field(
        description="Timestamp used to select the applicable daily exchange rate.",
    )
    target_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
        description="Foreign currency involved in the transaction.",
    )
    foreign_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=20,
        decimal_places=10,
        description="Amount of target_currency to buy or sell. Provide exactly one amount field.",
    )
    base_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=20,
        decimal_places=10,
        description="Amount in the store's home currency. Provide exactly one amount field.",
    )

    @field_validator("target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return normalize_currency_code(value)

    @model_validator(mode="after")
    def validate_amounts(self):
        if (self.foreign_amount is None) == (self.base_amount is None):
            raise ValueError("provide exactly one of foreign_amount or base_amount")
        return self


class BuyTransactionCreate(TransactionOperationFields):
    pass


class SellTransactionCreate(TransactionOperationFields):
    pass


class CrossSellTransactionCreate(BaseModel):
    """Convert one non-home currency into another through the home currency."""

    model_config = ConfigDict(extra="forbid")

    transaction_id: UUID | None = Field(
        default=None,
        description="Optional grouping ID shared by the two resulting transaction legs.",
    )
    transaction_timestamp: datetime = Field(
        description="Timestamp used to select both daily exchange rates.",
    )
    source_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
        description="The non-home currency being exchanged away.",
    )
    target_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
        description="The non-home currency being received.",
    )
    source_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=20,
        decimal_places=10,
        description="Amount of source_currency to exchange. Mutually exclusive with target_amount.",
    )
    target_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=20,
        decimal_places=10,
        description="Amount of target_currency to receive. Mutually exclusive with source_amount.",
    )

    @field_validator("source_currency", "target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return normalize_currency_code(value)

    @model_validator(mode="after")
    def validate_currency_pair(self):
        if self.source_currency == self.target_currency:
            raise ValueError("source_currency and target_currency must differ")
        return self

    @model_validator(mode="after")
    def validate_amounts(self):
        if (self.source_amount is None) == (self.target_amount is None):
            raise ValueError("provide exactly one of source_amount or target_amount")
        return self


class ForeignExchangeTransactionUpdate(ForeignExchangeTransactionFields):
    transaction_id: UUID | None = None


class ForeignExchangeTransactionResponse(ForeignExchangeTransactionFields):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Unique identifier for this persisted transaction leg.")
    transaction_id: UUID = Field(
        description="Identifier shared by both legs of a cross-sell transaction.",
    )
    created_at: datetime | None = Field(
        description="Timestamp when this transaction leg was persisted.",
    )

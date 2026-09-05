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
    rate_date: date
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
    exchange_rate: Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
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
    rates: list[ExchangeRateResponse]
    count: int


class ExchangeRateBatchDeleteResponse(BaseModel):
    rate_date: date
    base_currency: str
    deleted_count: int


class ForeignExchangeTransactionFields(BaseModel):
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
    effective_rate: Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
    )
    foreign_amount: Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
    )
    base_amount: Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
    )
    rounding_adjustment: Decimal | None = Field(
        default=None,
        max_digits=20,
        decimal_places=10,
    )
    fee: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=20,
        decimal_places=10,
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

    transaction_id: UUID | None = None
    transaction_timestamp: datetime
    target_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    )
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
    model_config = ConfigDict(extra="forbid")

    transaction_id: UUID | None = None
    transaction_timestamp: datetime
    source_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    )
    target_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    )
    source_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=20,
        decimal_places=10,
    )
    target_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=20,
        decimal_places=10,
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

    id: UUID
    transaction_id: UUID
    created_at: datetime | None

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

import pycountry
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExchangeRateSide(StrEnum):
    """Enumerate the BUY and SELL sides of an exchange rate."""

    BUY = "BUY"
    SELL = "SELL"


def normalize_currency_code(value: str) -> str:
    """Validate and normalize a three-letter ISO 4217 currency code."""
    currency_code = value.upper()
    if pycountry.currencies.get(alpha_3=currency_code) is None:
        raise ValueError("currency code must be a valid ISO 4217 code")
    return currency_code


class ExchangeRateFields(BaseModel):
    """Define the shared fields for exchange-rate records."""

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


class ExchangeRateCreate(ExchangeRateFields):
    """Validate an individual exchange-rate creation payload."""

    @field_validator("base_currency", "target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize both currencies in the exchange-rate payload."""
        return normalize_currency_code(value)


class ExchangeRateValueUpdate(BaseModel):
    """Represent an update to an exchange-rate value."""

    exchange_rate: Decimal = Field(gt=0, max_digits=20, decimal_places=10)


class ExchangeRateBatchItem(BaseModel):
    """Represent one target-currency rate within a batch."""

    target_currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    exchange_rate: Decimal = Field(gt=0, max_digits=20, decimal_places=10)
    side: ExchangeRateSide

    @field_validator("target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize the batch item's target currency."""
        return normalize_currency_code(value)


class ExchangeRateBatchCreate(BaseModel):
    """Validate a complete daily exchange-rate creation payload."""

    rate_date: date
    base_currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    rates: list[ExchangeRateBatchItem] = Field(min_length=1, max_length=500)

    @field_validator("base_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize the batch base currency."""
        return normalize_currency_code(value)

    @model_validator(mode="after")
    def validate_unique_targets(self):
        """Reject duplicate rate sides and targets matching the base currency."""
        pairs = [(item.target_currency, item.side) for item in self.rates]
        if len(pairs) != len(set(pairs)):
            raise ValueError("rates must not contain duplicate target_currency and side values")
        if self.base_currency in {item.target_currency for item in self.rates}:
            raise ValueError("target_currency must differ from base_currency")
        return self


class ExchangeRateBatchUpdate(BaseModel):
    """Validate a complete replacement payload for a daily rate set."""

    rates: list[ExchangeRateBatchItem] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_unique_targets(self):
        """Reject duplicate target-currency and side combinations."""
        pairs = [(item.target_currency, item.side) for item in self.rates]
        if len(pairs) != len(set(pairs)):
            raise ValueError("rates must not contain duplicate target_currency and side values")
        return self


class ExchangeRateResponse(ExchangeRateFields):
    """Represent an exchange-rate record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime | None


class ExchangeRateBatchResponse(BaseModel):
    """Represent the rates created or returned by a batch operation."""

    rates: list[ExchangeRateResponse] = Field(description="The exchange-rate records in the batch.")
    count: int = Field(description="Number of records in rates.")


class ExchangeRateBatchDeleteResponse(BaseModel):
    """Report the daily rate set deletion result."""

    rate_date: date = Field(description="Date whose rates were deleted.")
    base_currency: str = Field(description="Base currency whose daily rates were deleted.")
    deleted_count: int = Field(description="Number of rate records deleted.")

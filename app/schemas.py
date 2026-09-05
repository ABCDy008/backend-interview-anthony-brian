from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    exchange_rate: Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
    )

    @field_validator("base_currency", "target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class ExchangeRateCreate(ExchangeRateFields):
    pass


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

    @field_validator("target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


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
        return value.upper()

    @model_validator(mode="after")
    def validate_unique_targets(self):
        targets = [item.target_currency for item in self.rates]
        if len(targets) != len(set(targets)):
            raise ValueError("rates must not contain duplicate target_currency values")
        if self.base_currency in targets:
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
        return value.upper()

    @model_validator(mode="after")
    def validate_unique_targets(self):
        targets = [item.target_currency for item in self.rates]
        if len(targets) != len(set(targets)):
            raise ValueError("rates must not contain duplicate target_currency values")
        if self.base_currency in targets:
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

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class DailyRateCreate(BaseModel):
    rate_date: date
    base_currency: str = Field(min_length=3, max_length=3)
    quote_currency: str = Field(min_length=3, max_length=3)
    side: Side
    rate: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def normalize_currencies(self):
        self.base_currency = self.base_currency.upper()
        self.quote_currency = self.quote_currency.upper()
        if self.base_currency == self.quote_currency:
            raise ValueError("base_currency and quote_currency must differ")
        return self


class DailyRateResponse(DailyRateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RateCreate(BaseModel):
    currency_code: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    currency_name: str = Field(min_length=1, max_length=50)
    rate_per_usd: Decimal = Field(gt=0, max_digits=18, decimal_places=6)

    @model_validator(mode="after")
    def normalize_currency(self):
        self.currency_code = self.currency_code.upper()
        return self


class USDExchangeRateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    currency_code: str
    currency_name: str
    rate_per_usd: Decimal
    last_updated_at: datetime | None


class TransactionCreate(BaseModel):
    transaction_timestamp: datetime
    base_currency: str = Field(min_length=3, max_length=3)
    quote_currency: str = Field(min_length=3, max_length=3)
    side: Side
    foreign_amount: Decimal | None = Field(default=None, gt=0)
    base_amount: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_amounts(self):
        if (self.foreign_amount is None) == (self.base_amount is None):
            raise ValueError("provide exactly one of foreign_amount or base_amount")
        self.base_currency = self.base_currency.upper()
        self.quote_currency = self.quote_currency.upper()
        if self.base_currency == self.quote_currency:
            raise ValueError("base_currency and quote_currency must differ")
        return self


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    transaction_id: str
    transaction_timestamp: datetime
    base_currency: str
    quote_currency: str
    side: Side
    foreign_amount: Decimal
    base_amount: Decimal
    effective_rate: Decimal
    fee_amount: Decimal
    rounding_adjustment: Decimal

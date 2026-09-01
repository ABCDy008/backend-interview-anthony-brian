import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import CHAR, Date, DateTime, Enum, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TradeSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class DailyRate(Base):
    __tablename__ = "daily_rates"
    __table_args__ = (UniqueConstraint("rate_date", "base_currency", "quote_currency", "side"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rate_date: Mapped[date] = mapped_column(Date, index=True)
    base_currency: Mapped[str] = mapped_column(String(3))
    quote_currency: Mapped[str] = mapped_column(String(3))
    side: Mapped[TradeSide] = mapped_column(Enum(TradeSide))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8))


class USDExchangeRate(Base):
    __tablename__ = "usd_exchange_rates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    currency_code: Mapped[str] = mapped_column(CHAR(3), nullable=False, unique=True)
    currency_name: Mapped[str] = mapped_column(String(50), nullable=False)
    rate_per_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FXTransaction(Base):
    __tablename__ = "fx_transactions"

    transaction_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    transaction_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    base_currency: Mapped[str] = mapped_column(String(3))
    quote_currency: Mapped[str] = mapped_column(String(3))
    side: Mapped[TradeSide] = mapped_column(Enum(TradeSide))
    foreign_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    effective_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    rounding_adjustment: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))

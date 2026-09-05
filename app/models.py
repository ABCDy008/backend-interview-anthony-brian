import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint(
            "rate_date",
            "base_currency",
            "target_currency",
            "side",
            name="unique_daily_pair",
        ),
        CheckConstraint("side IN ('BUY', 'SELL')", name="valid_exchange_rate_side"),
        Index(
            "idx_exchange_rates_lookup",
            "rate_date",
            "base_currency",
            "target_currency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("uuidv7()"),
    )
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    target_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )

class Transaction(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("uuidv7()"),
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        server_default=text("uuidv7()"),
    )
    transaction_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class ForeignExchangeTransaction(Transaction):
    __tablename__ = "foreign_exchange_transactions"
    __table_args__ = (
        CheckConstraint(
            "side IN ('BUY', 'SELL')",
            name="valid_foreign_exchange_transaction_side",
        ),
        CheckConstraint(
            "foreign_amount > 0",
            name="positive_foreign_exchange_transaction_foreign_amount",
        ),
        CheckConstraint(
            "effective_rate > 0",
            name="positive_foreign_exchange_transaction_effective_rate",
        ),
        CheckConstraint(
            "base_amount > 0",
            name="positive_foreign_exchange_transaction_base_amount",
        ),
        CheckConstraint(
            "rounded_amount IS NULL OR rounded_amount >= 0",
            name="non_negative_foreign_exchange_transaction_rounded_amount",
        ),
        CheckConstraint(
            "fee IS NULL OR fee >= 0",
            name="non_negative_foreign_exchange_transaction_fee",
        ),
        Index("idx_foreign_exchange_transactions_transaction_id", "transaction_id"),
        Index(
            "idx_foreign_exchange_transactions_lookup",
            "base_currency",
            "target_currency",
            "side",
        ),
    )

    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    target_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    effective_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    foreign_amount: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    rounded_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))


__all__ = [
    "ExchangeRate",
    "ForeignExchangeTransaction",
    "Transaction",
]


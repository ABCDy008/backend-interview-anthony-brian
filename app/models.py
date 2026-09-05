import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint(
            "rate_date",
            "base_currency",
            "target_currency",
            name="unique_daily_pair",
        ),
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
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(), server_default=text("NOW()")
    )

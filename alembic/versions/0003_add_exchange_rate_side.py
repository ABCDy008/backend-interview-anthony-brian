"""add buy and sell sides to exchange rates

Revision ID: 0003_exchange_rate_side
Revises: 0002_uuidv7_exchange_rates
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_exchange_rate_side"
down_revision: str | Sequence[str] | None = "0002_uuidv7_exchange_rates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exchange_rates",
        sa.Column("side", sa.String(length=4), nullable=False, server_default="BUY"),
    )
    op.alter_column("exchange_rates", "side", server_default=None)
    op.drop_index("idx_exchange_rates_lookup", table_name="exchange_rates")
    op.drop_constraint("unique_daily_pair", "exchange_rates", type_="unique")
    op.create_unique_constraint(
        "unique_daily_pair",
        "exchange_rates",
        ["rate_date", "base_currency", "target_currency", "side"],
    )
    op.create_check_constraint(
        "valid_exchange_rate_side",
        "exchange_rates",
        "side IN ('BUY', 'SELL')",
    )
    op.create_index(
        "idx_exchange_rates_lookup",
        "exchange_rates",
        ["rate_date", "base_currency", "target_currency", "side"],
    )


def downgrade() -> None:
    op.drop_index("idx_exchange_rates_lookup", table_name="exchange_rates")
    op.drop_constraint("valid_exchange_rate_side", "exchange_rates", type_="check")
    op.drop_constraint("unique_daily_pair", "exchange_rates", type_="unique")
    op.create_unique_constraint(
        "unique_daily_pair",
        "exchange_rates",
        ["rate_date", "base_currency", "target_currency"],
    )
    op.create_index(
        "idx_exchange_rates_lookup",
        "exchange_rates",
        ["rate_date", "base_currency", "target_currency"],
    )
    op.drop_column("exchange_rates", "side")
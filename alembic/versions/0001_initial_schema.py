"""create initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "exchange_rates",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("target_currency", sa.String(length=3), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rate_date", "base_currency", "target_currency",
            name="unique_daily_pair",
        ),
    )
    op.create_index(
        "idx_exchange_rates_lookup",
        "exchange_rates",
        ["rate_date", "base_currency", "target_currency"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_exchange_rates_lookup", table_name="exchange_rates")
    op.drop_table("exchange_rates")

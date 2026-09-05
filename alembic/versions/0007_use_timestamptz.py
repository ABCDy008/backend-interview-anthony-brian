"""use timezone-aware transaction timestamps

Revision ID: 0007_timestamptz
Revises: 0006_transaction_timestamp
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_timestamptz"
down_revision: str | Sequence[str] | None = "0006_transaction_timestamp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "exchange_rates",
        "created_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "foreign_exchange_transactions",
        "transaction_timestamp",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="transaction_timestamp AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "foreign_exchange_transactions",
        "created_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "foreign_exchange_transactions",
        "created_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "foreign_exchange_transactions",
        "transaction_timestamp",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="transaction_timestamp AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "exchange_rates",
        "created_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
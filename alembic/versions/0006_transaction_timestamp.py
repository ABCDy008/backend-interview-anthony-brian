"""rename transaction date to transaction timestamp

Revision ID: 0006_transaction_timestamp
Revises: 0005_fx_transaction_date
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_transaction_timestamp"
down_revision: str | Sequence[str] | None = "0005_fx_transaction_date"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "foreign_exchange_transactions",
        "transaction_date",
        new_column_name="transaction_timestamp",
        existing_type=sa.Date(),
        existing_nullable=False,
    )
    op.alter_column(
        "foreign_exchange_transactions",
        "transaction_timestamp",
        type_=sa.DateTime(),
        existing_type=sa.Date(),
        existing_nullable=False,
        postgresql_using="transaction_timestamp::timestamp",
    )


def downgrade() -> None:
    op.alter_column(
        "foreign_exchange_transactions",
        "transaction_timestamp",
        type_=sa.Date(),
        existing_type=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="transaction_timestamp::date",
    )
    op.alter_column(
        "foreign_exchange_transactions",
        "transaction_timestamp",
        new_column_name="transaction_date",
        existing_type=sa.Date(),
        existing_nullable=False,
    )
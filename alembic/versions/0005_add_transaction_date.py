"""add transaction date to foreign exchange transactions

Revision ID: 0005_fx_transaction_date
Revises: 0004_fx_transactions
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_fx_transaction_date"
down_revision: str | Sequence[str] | None = "0004_fx_transactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "foreign_exchange_transactions",
        sa.Column("transaction_date", sa.Date(), nullable=True),
    )
    op.execute(
        """
        UPDATE foreign_exchange_transactions
        SET transaction_date = COALESCE(created_at::date, CURRENT_DATE)
        WHERE transaction_date IS NULL
        """
    )
    op.alter_column("foreign_exchange_transactions", "transaction_date", nullable=False)


def downgrade() -> None:
    op.drop_column("foreign_exchange_transactions", "transaction_date")
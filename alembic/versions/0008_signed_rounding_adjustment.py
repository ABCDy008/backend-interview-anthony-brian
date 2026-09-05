"""store signed rounding adjustments

Revision ID: 0008_signed_rounding_adjustment
Revises: 0007_timestamptz
Create Date: 2026-09-06
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0008_signed_rounding_adjustment"
down_revision: str | Sequence[str] | None = "0007_timestamptz"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "non_negative_foreign_exchange_transaction_rounded_amount",
        "foreign_exchange_transactions",
        type_="check",
    )
    op.alter_column(
        "foreign_exchange_transactions",
        "rounded_amount",
        new_column_name="rounding_adjustment",
    )


def downgrade() -> None:
    op.alter_column(
        "foreign_exchange_transactions",
        "rounding_adjustment",
        new_column_name="rounded_amount",
    )
    op.create_check_constraint(
        "non_negative_foreign_exchange_transaction_rounded_amount",
        "foreign_exchange_transactions",
        "rounded_amount IS NULL OR rounded_amount >= 0",
    )
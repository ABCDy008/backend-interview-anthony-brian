"""create foreign exchange transactions

Revision ID: 0004_fx_transactions
Revises: 0003_exchange_rate_side
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_fx_transactions"
down_revision: str | Sequence[str] | None = "0003_exchange_rate_side"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "foreign_exchange_transactions",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column(
            "transaction_id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("target_currency", sa.String(length=3), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column(
            "effective_rate",
            sa.Numeric(precision=20, scale=10),
            nullable=False,
        ),
        sa.Column(
            "foreign_amount",
            sa.Numeric(precision=20, scale=10),
            nullable=False,
        ),
        sa.Column(
            "base_amount",
            sa.Numeric(precision=20, scale=10),
            nullable=False,
        ),
        sa.Column("rounded_amount", sa.Numeric(precision=20, scale=10)),
        sa.Column("fee", sa.Numeric(precision=20, scale=10)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "side IN ('BUY', 'SELL')",
            name="valid_foreign_exchange_transaction_side",
        ),
        sa.CheckConstraint(
            "foreign_amount > 0",
            name="positive_foreign_exchange_transaction_foreign_amount",
        ),
        sa.CheckConstraint(
            "effective_rate > 0",
            name="positive_foreign_exchange_transaction_effective_rate",
        ),
        sa.CheckConstraint(
            "base_amount > 0",
            name="positive_foreign_exchange_transaction_base_amount",
        ),
        sa.CheckConstraint(
            "rounded_amount IS NULL OR rounded_amount >= 0",
            name="non_negative_foreign_exchange_transaction_rounded_amount",
        ),
        sa.CheckConstraint(
            "fee IS NULL OR fee >= 0",
            name="non_negative_foreign_exchange_transaction_fee",
        ),
    )
    op.create_index(
        "idx_foreign_exchange_transactions_transaction_id",
        "foreign_exchange_transactions",
        ["transaction_id"],
    )
    op.create_index(
        "idx_foreign_exchange_transactions_lookup",
        "foreign_exchange_transactions",
        ["base_currency", "target_currency", "side"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_foreign_exchange_transactions_lookup",
        table_name="foreign_exchange_transactions",
    )
    op.drop_index(
        "idx_foreign_exchange_transactions_transaction_id",
        table_name="foreign_exchange_transactions",
    )
    op.drop_table("foreign_exchange_transactions")
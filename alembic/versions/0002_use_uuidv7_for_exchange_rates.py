"""use PostgreSQL UUIDv7 generation for exchange rates

Revision ID: 0002_uuidv7_exchange_rates
Revises: 0001_initial_schema
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_uuidv7_exchange_rates"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "exchange_rates",
        "id",
        server_default=sa.text("uuidv7()"),
    )


def downgrade() -> None:
    op.alter_column(
        "exchange_rates",
        "id",
        server_default=sa.text("uuid_generate_v4()"),
    )
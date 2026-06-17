"""add passwordless site signin

Revision ID: 11d7fd8d25e4
Revises: 704f4e95f8bf
Create Date: 2026-06-16 15:08:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "11d7fd8d25e4"
down_revision: str | Sequence[str] | None = "704f4e95f8bf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("signin_code", sa.Text(), nullable=True))
    op.add_column("sites", sa.Column("signin_code_expires", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("sites", "signin_code_expires")
    op.drop_column("sites", "signin_code")

"""add uploads

Revision ID: cc1b1360d6ec
Revises: 11d7fd8d25e4
Create Date: 2026-11-03 11:50:23.280053

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cc1b1360d6ec"
down_revision: str | Sequence[str] | None = "11d7fd8d25e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uploads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column(
            "created",
            sa.DateTime(),
            server_default=sa.text("(current_timestamp at time zone 'utc')"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(op.f("ix_uploads_site_id"), "uploads", ["site_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_uploads_site_id"), table_name="uploads")
    op.drop_table("uploads")

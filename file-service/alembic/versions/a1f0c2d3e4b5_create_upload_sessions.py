"""create upload sessions

Revision ID: a1f0c2d3e4b5
Revises:
Create Date: 2026-11-06 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1f0c2d3e4b5"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("upload_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("file_path", sa.String(length=255), nullable=True),
        sa.Column("ticket", sa.Text(), nullable=False),
        sa.Column("completed_event_id", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("upload_id", name="pk_upload_sessions"),
    )
    op.create_index(
        "ix_upload_sessions_status_last_activity_at",
        "upload_sessions",
        ["status", "last_activity_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_upload_sessions_status_last_activity_at", table_name="upload_sessions")
    op.drop_table("upload_sessions")

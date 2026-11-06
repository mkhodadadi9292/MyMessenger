"""add upload_id to artifacts

Revision ID: d7b3f1a2c9e4
Revises: c4e7a1b9d2f3
Create Date: 2026-11-06 13:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'd7b3f1a2c9e4'
down_revision: str | Sequence[str] | None = 'c4e7a1b9d2f3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('artifacts', sa.Column('upload_id', sa.String(length=32), nullable=True))
    op.create_index('ux_artifacts_upload_id', 'artifacts', ['upload_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ux_artifacts_upload_id', table_name='artifacts')
    op.drop_column('artifacts', 'upload_id')

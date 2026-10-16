"""add message reactions

Revision ID: c4e7a1b9d2f3
Revises: 668d0e5321c7
Create Date: 2026-10-16 10:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e7a1b9d2f3'
down_revision: Union[str, Sequence[str], None] = '668d0e5321c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'message_reactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id', 'user_id', name='uq_message_reactions_message_user'),
    )
    op.create_index(
        op.f('ix_message_reactions_message_id'), 'message_reactions', ['message_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_message_reactions_message_id'), table_name='message_reactions')
    op.drop_table('message_reactions')
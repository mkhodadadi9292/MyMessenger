"""add notifications

Revision ID: a7e5f9c2d4b1
Revises: c4e7a1b9d2f3
Create Date: 2026-10-23 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7e5f9c2d4b1'
down_revision: Union[str, Sequence[str], None] = 'c4e7a1b9d2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=16), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('invite_id', sa.Integer(), nullable=True),
        sa.Column('chat_title', sa.String(length=255), nullable=True),
        sa.Column('preview', sa.Text(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invite_id'], ['group_invites.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notifications_chat_id'), 'notifications', ['chat_id'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_notifications_message_id'), 'notifications', ['message_id'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_message_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_chat_id'), table_name='notifications')
    op.drop_table('notifications')

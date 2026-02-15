"""add user roles table for RBAC

Revision ID: 0003_add_user_roles
Revises: 0002_add_revoked_tokens
Create Date: 2026-02-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0003_add_user_roles'
down_revision: Union[str, None] = '0002_add_revoked_tokens'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_roles',
        sa.Column('user_id', sa.String(length=64), primary_key=True),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_user_roles_role', 'user_roles', ['role'])


def downgrade() -> None:
    op.drop_index('ix_user_roles_role', table_name='user_roles')
    op.drop_table('user_roles')

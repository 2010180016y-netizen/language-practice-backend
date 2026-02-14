"""add revoked token table and import created_at index

Revision ID: 0002_add_revoked_tokens
Revises: 0001_create_import_tables
Create Date: 2026-02-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0002_add_revoked_tokens'
down_revision: Union[str, None] = '0001_create_import_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_import_jobs_created_at', 'import_jobs', ['created_at'])

    op.create_table(
        'revoked_tokens',
        sa.Column('jti', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('token_type', sa.String(length=16), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_revoked_tokens_user_id', 'revoked_tokens', ['user_id'])
    op.create_index('ix_revoked_tokens_token_type', 'revoked_tokens', ['token_type'])
    op.create_index('ix_revoked_tokens_expires_at', 'revoked_tokens', ['expires_at'])


def downgrade() -> None:
    op.drop_index('ix_revoked_tokens_expires_at', table_name='revoked_tokens')
    op.drop_index('ix_revoked_tokens_token_type', table_name='revoked_tokens')
    op.drop_index('ix_revoked_tokens_user_id', table_name='revoked_tokens')
    op.drop_table('revoked_tokens')

    op.drop_index('ix_import_jobs_created_at', table_name='import_jobs')

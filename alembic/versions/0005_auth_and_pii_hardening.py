"""add credentials table and pii-safe import fields

Revision ID: 0005_auth_and_pii_hardening
Revises: 0004_async_reliability_and_indexes
Create Date: 2026-02-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0005_auth_and_pii_hardening'
down_revision: Union[str, None] = '0004_async_reliability_and_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_credentials',
        sa.Column('user_id', sa.String(length=64), primary_key=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.add_column('import_jobs', sa.Column('content_sha256', sa.String(length=64), nullable=True))
    op.add_column('import_jobs', sa.Column('content_preview_masked', sa.Text(), nullable=True))
    op.create_index('ix_import_jobs_content_sha256', 'import_jobs', ['content_sha256'])


def downgrade() -> None:
    op.drop_index('ix_import_jobs_content_sha256', table_name='import_jobs')
    op.drop_column('import_jobs', 'content_preview_masked')
    op.drop_column('import_jobs', 'content_sha256')
    op.drop_table('user_credentials')

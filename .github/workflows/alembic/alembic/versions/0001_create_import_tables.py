"""create import and idempotency tables

Revision ID: 0001_create_import_tables
Revises: 
Create Date: 2026-02-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0001_create_import_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'import_jobs',
        sa.Column('job_id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('progress_percent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('channel', sa.String(length=32), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_import_jobs_user_id', 'import_jobs', ['user_id'])
    op.create_index('ix_import_jobs_status', 'import_jobs', ['status'])

    op.create_table(
        'idempotency_keys',
        sa.Column('key', sa.String(length=128), primary_key=True),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('job_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_idempotency_keys_user_id', 'idempotency_keys', ['user_id'])
    op.create_index('ix_idempotency_keys_job_id', 'idempotency_keys', ['job_id'])


def downgrade() -> None:
    op.drop_index('ix_idempotency_keys_job_id', table_name='idempotency_keys')
    op.drop_index('ix_idempotency_keys_user_id', table_name='idempotency_keys')
    op.drop_table('idempotency_keys')

    op.drop_index('ix_import_jobs_status', table_name='import_jobs')
    op.drop_index('ix_import_jobs_user_id', table_name='import_jobs')
    op.drop_table('import_jobs')

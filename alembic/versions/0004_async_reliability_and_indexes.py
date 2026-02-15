"""add async reliability columns and indexes

Revision ID: 0004_async_reliability_and_indexes
Revises: 0003_add_user_roles
Create Date: 2026-02-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0004_async_reliability_and_indexes'
down_revision: Union[str, None] = '0003_add_user_roles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('import_jobs', sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('import_jobs', sa.Column('last_error', sa.Text(), nullable=True))
    op.add_column('import_jobs', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE import_jobs SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column('import_jobs', 'updated_at', nullable=False)

    op.create_index('ix_import_jobs_user_status_created_at', 'import_jobs', ['user_id', 'status', 'created_at'])
    op.create_index('ix_import_jobs_updated_at', 'import_jobs', ['updated_at'])


def downgrade() -> None:
    op.drop_index('ix_import_jobs_updated_at', table_name='import_jobs')
    op.drop_index('ix_import_jobs_user_status_created_at', table_name='import_jobs')

    op.drop_column('import_jobs', 'updated_at')
    op.drop_column('import_jobs', 'last_error')
    op.drop_column('import_jobs', 'attempts')

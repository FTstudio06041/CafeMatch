"""add system_settings

Revision ID: f823bd42ac50
Revises:
Create Date: 2026-06-30 20:49:19.190390

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f823bd42ac50'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'system_settings',
        sa.Column('setting_key', sa.String(length=100), nullable=False),
        sa.Column('setting_value', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('setting_key'),
    )


def downgrade():
    op.drop_table('system_settings')

"""add user module permissions

Revision ID: 8d4e6f1a2b30
Revises: 7c1d2e3f4a50
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa

revision = '8d4e6f1a2b30'
down_revision = '7c1d2e3f4a50'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_module',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('module_key', sa.String(length=40), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='viewer'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'module_key', name='uq_user_module'),
    )
    op.create_index(op.f('ix_user_module_user_id'), 'user_module', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_module_module_key'), 'user_module', ['module_key'], unique=False)

    # Agenda remains the base module for all existing users.
    op.execute("""
        INSERT INTO user_module (user_id, module_key, enabled, role)
        SELECT id, 'agenda', true, CASE WHEN role = 'admin' THEN 'admin' ELSE 'user' END
        FROM "user"
    """)


def downgrade():
    op.drop_index(op.f('ix_user_module_module_key'), table_name='user_module')
    op.drop_index(op.f('ix_user_module_user_id'), table_name='user_module')
    op.drop_table('user_module')

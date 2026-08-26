"""add training team code

Revision ID: 4a2c9b7d8e01
Revises: 0b71e561a5c9
Create Date: 2026-06-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a2c9b7d8e01'
down_revision = '0b71e561a5c9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('training', schema=None) as batch_op:
        batch_op.add_column(sa.Column('team_code', sa.String(length=32), nullable=True, server_default='SENIORS'))

    op.execute("UPDATE training SET team_code = 'SENIORS' WHERE team_code IS NULL OR team_code = ''")

    with op.batch_alter_table('training', schema=None) as batch_op:
        batch_op.alter_column('team_code', existing_type=sa.String(length=32), nullable=False, server_default='SENIORS')
        batch_op.create_index(batch_op.f('ix_training_team_code'), ['team_code'], unique=False)


def downgrade():
    with op.batch_alter_table('training', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_training_team_code'))
        batch_op.drop_column('team_code')

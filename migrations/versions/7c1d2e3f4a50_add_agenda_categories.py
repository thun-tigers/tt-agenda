"""add agenda categories and attendance policies

Revision ID: 7c1d2e3f4a50
Revises: 4a2c9b7d8e01
Create Date: 2026-07-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '7c1d2e3f4a50'
down_revision = '4a2c9b7d8e01'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('training', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(length=20), nullable=True, server_default='training'))
        batch_op.create_index(batch_op.f('ix_training_category'), ['category'], unique=False)

    op.execute("UPDATE training SET category = 'training' WHERE category IS NULL OR category = ''")

    with op.batch_alter_table('training', schema=None) as batch_op:
        batch_op.alter_column('category', existing_type=sa.String(length=20), nullable=False, server_default='training')

    op.create_table(
        'agenda_category',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=40), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=False, server_default='bi-calendar-event'),
        sa.Column('badge_class', sa.String(length=200), nullable=False, server_default='bg-slate-100 text-slate-700'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('attendance_required_for', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('attendance_allowed_for', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('show_presence_tracking', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )

    categories = sa.table(
        'agenda_category',
        sa.column('key', sa.String),
        sa.column('label', sa.String),
        sa.column('icon', sa.String),
        sa.column('badge_class', sa.String),
        sa.column('sort_order', sa.Integer),
        sa.column('attendance_required_for', sa.Text),
        sa.column('attendance_allowed_for', sa.Text),
        sa.column('show_presence_tracking', sa.Boolean),
    )
    op.bulk_insert(categories, [
        {'key': 'training', 'label': 'Training', 'icon': 'bi-calendar-event', 'badge_class': 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300', 'sort_order': 1, 'attendance_required_for': '["player"]', 'attendance_allowed_for': '["player"]', 'show_presence_tracking': True},
        {'key': 'game', 'label': 'Saison-Spiel', 'icon': 'bi-trophy-fill', 'badge_class': 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300', 'sort_order': 2, 'attendance_required_for': '["player", "coach", "team_manager"]', 'attendance_allowed_for': '["player", "coach", "team_manager"]', 'show_presence_tracking': True},
        {'key': 'event', 'label': 'Event', 'icon': 'bi-stars', 'badge_class': 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300', 'sort_order': 3, 'attendance_required_for': '["coach", "team_manager"]', 'attendance_allowed_for': '["player", "coach", "team_manager"]', 'show_presence_tracking': True},
    ])


def downgrade():
    op.drop_table('agenda_category')
    with op.batch_alter_table('training', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_training_category'))
        batch_op.drop_column('category')

"""add profile activity tracking

Revision ID: 0003_profile_activity
Revises: 0002_stars_photo_moderation
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_profile_activity"
down_revision = "0002_stars_photo_moderation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("last_active_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("last_inactive_reminder_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("inactive_reminder_stage", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_users_last_active_at", "users", ["last_active_at"])
    op.execute("UPDATE users SET last_active_at = COALESCE(updated_at, created_at) WHERE last_active_at IS NULL")
    op.alter_column("users", "inactive_reminder_stage", server_default=None)


def downgrade():
    op.drop_index("ix_users_last_active_at", table_name="users")
    op.drop_column("users", "inactive_reminder_stage")
    op.drop_column("users", "last_inactive_reminder_at")
    op.drop_column("users", "last_active_at")

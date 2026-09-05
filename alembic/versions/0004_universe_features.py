"""universe features: questions, blind dates and interests

Revision ID: 0004_universe_features
Revises: 0003_profile_activity
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_universe_features"
down_revision = "0003_profile_activity"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("interests", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("daily_question_answer", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("daily_question_date", sa.DateTime(), nullable=True))
    op.create_table(
        "blind_dates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_a_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_b_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revealed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_a_id", "user_b_id", name="uq_blind_dates_pair"),
    )
    op.create_index("ix_blind_dates_status", "blind_dates", ["status"])


def downgrade():
    op.drop_index("ix_blind_dates_status", table_name="blind_dates")
    op.drop_table("blind_dates")
    op.drop_column("users", "daily_question_date")
    op.drop_column("users", "daily_question_answer")
    op.drop_column("users", "interests")

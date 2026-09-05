"""add internal Stars and photo moderation fields

Revision ID: 0002_stars_photo_moderation
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_stars_photo_moderation"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("stars_balance", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("photos", sa.Column("moderation_reason", sa.String(500), nullable=True))
    op.add_column("photos", sa.Column("moderation_score", sa.Float(), nullable=True))
    op.add_column("photos", sa.Column("moderated_at", sa.DateTime(), nullable=True))
    op.add_column("photos", sa.Column("moderation_source", sa.String(20), nullable=True))
    op.create_index("ix_photos_moderation_source", "photos", ["moderation_source"])
    op.create_table(
        "star_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("admin_tg_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_star_transactions_user_id", "star_transactions", ["user_id"])
    op.create_index("ix_star_transactions_created_at", "star_transactions", ["created_at"])
    op.alter_column("users", "stars_balance", server_default=None)


def downgrade():
    op.drop_index("ix_star_transactions_created_at", table_name="star_transactions")
    op.drop_index("ix_star_transactions_user_id", table_name="star_transactions")
    op.drop_table("star_transactions")
    op.drop_index("ix_photos_moderation_source", table_name="photos")
    op.drop_column("photos", "moderation_source")
    op.drop_column("photos", "moderated_at")
    op.drop_column("photos", "moderation_score")
    op.drop_column("photos", "moderation_reason")
    op.drop_column("users", "stars_balance")

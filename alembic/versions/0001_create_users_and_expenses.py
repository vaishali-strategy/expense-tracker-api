"""create users and expenses

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

CATEGORIES = "'groceries', 'leisure', 'electronics', 'utilities', 'clothing', 'health', 'others'"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("spent_at", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        sa.CheckConstraint(f"category IN ({CATEGORIES})", name="ck_expenses_category"),
    )
    op.create_index("ix_expenses_user_spent", "expenses", ["user_id", "spent_at"])


def downgrade() -> None:
    op.drop_index("ix_expenses_user_spent", table_name="expenses")
    op.drop_table("expenses")
    op.drop_table("users")

"""Database tables: users and their expenses."""

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Category(str, enum.Enum):
    groceries = "groceries"
    leisure = "leisure"
    electronics = "electronics"
    utilities = "utilities"
    clothing = "clothing"
    health = "health"
    others = "others"


CATEGORY_VALUES = ", ".join(f"'{c.value}'" for c in Category)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    category: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(200), default="")
    spent_at: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint(f"category IN ({CATEGORY_VALUES})", name="ck_expenses_category"),
        # Every list and report query filters by user and a date range, so this is the index
        # that matters (see scripts/index_benchmark.py for the measurement).
        Index("ix_expenses_user_spent", "user_id", "spent_at"),
    )

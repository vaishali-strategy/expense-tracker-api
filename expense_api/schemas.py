"""Request and response shapes (what the API accepts and returns)."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from expense_api.models import Category


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


Money = Field(gt=0, max_digits=12, decimal_places=2, description="Amount with at most 2 decimals")


class ExpenseCreate(BaseModel):
    amount: Decimal = Money
    category: Category
    description: str = Field("", max_length=200)
    spent_at: date = Field(default_factory=date.today, description="Defaults to today")


class ExpenseUpdate(BaseModel):
    """Every field is optional: only the ones you send are changed."""

    amount: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=2)
    category: Category | None = None
    description: str | None = Field(None, max_length=200)
    spent_at: date | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: Decimal
    category: Category
    description: str
    spent_at: date
    created_at: datetime


class ExpensePage(BaseModel):
    items: list[ExpenseOut]
    total: int = Field(description="How many expenses match the filters (ignoring limit/offset)")
    limit: int
    offset: int


class Period(str, Enum):
    week = "week"  # the last 7 days, including today
    month = "month"  # the last 30 days, including today
    three_months = "3months"  # the last 90 days, including today


class CategoryTotal(BaseModel):
    category: Category
    total: Decimal
    count: int


class MonthTotal(BaseModel):
    month: str = Field(description="YYYY-MM")
    total: Decimal
    categories: list[CategoryTotal] = Field(description="Largest total first")


class MonthlyReport(BaseModel):
    year: int
    grand_total: Decimal
    months: list[MonthTotal] = Field(description="Only months that have expenses, oldest first")

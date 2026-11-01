"""Create, read, update, delete and filter a user's own expenses."""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.deps import CurrentUser, DbSession
from app.models import Category, Expense
from app.schemas import ExpenseCreate, ExpenseOut, ExpensePage, ExpenseUpdate, Period

router = APIRouter(prefix="/expenses", tags=["expenses"])

PERIOD_DAYS = {Period.week: 7, Period.month: 30, Period.three_months: 90}


def _get_own(db: DbSession, user: CurrentUser, expense_id: int) -> Expense:
    """The expense, only if it belongs to the caller. Someone else's expense is a 404, not a 403,
    so the API never reveals which ids exist."""
    expense = db.scalar(select(Expense).where(Expense.id == expense_id, Expense.user_id == user.id))
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    return expense


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(body: ExpenseCreate, db: DbSession, user: CurrentUser) -> Expense:
    data = body.model_dump()
    data["category"] = body.category.value  # store the plain text, not the enum object
    expense = Expense(user_id=user.id, **data)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.get("", response_model=ExpensePage)
def list_expenses(
    db: DbSession,
    user: CurrentUser,
    period: Annotated[Period | None, Query(description="Shortcut for a date range ending today")] = None,
    start_date: Annotated[date | None, Query(description="Inclusive. Cannot be combined with period")] = None,
    end_date: Annotated[date | None, Query(description="Inclusive. Cannot be combined with period")] = None,
    category: Category | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExpensePage:
    if period is not None and (start_date or end_date):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use either period or start_date/end_date")
    if period is not None:
        today = date.today()
        start_date, end_date = today - timedelta(days=PERIOD_DAYS[period] - 1), today
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "end_date is before start_date")

    conditions = [Expense.user_id == user.id]
    if start_date:
        conditions.append(Expense.spent_at >= start_date)
    if end_date:
        conditions.append(Expense.spent_at <= end_date)
    if category:
        conditions.append(Expense.category == category.value)

    total = db.scalar(select(func.count()).select_from(Expense).where(*conditions)) or 0
    items = db.scalars(
        select(Expense)
        .where(*conditions)
        .order_by(Expense.spent_at.desc(), Expense.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ExpensePage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{expense_id}", response_model=ExpenseOut)
def get_expense(expense_id: int, db: DbSession, user: CurrentUser) -> Expense:
    return _get_own(db, user, expense_id)


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: int, body: ExpenseUpdate, db: DbSession, user: CurrentUser) -> Expense:
    changes = body.model_dump(exclude_unset=True)
    if not changes or any(v is None for v in changes.values()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Send at least one field, and no nulls")
    if "category" in changes:
        changes["category"] = changes["category"].value
    expense = _get_own(db, user, expense_id)
    for field, value in changes.items():
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: DbSession, user: CurrentUser) -> Response:
    expense = _get_own(db, user, expense_id)
    db.delete(expense)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

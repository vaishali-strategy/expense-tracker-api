"""Monthly totals per category."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import extract, func, select

from expense_api.deps import CurrentUser, DbSession
from expense_api.models import Expense
from expense_api.schemas import CategoryTotal, MonthlyReport, MonthTotal

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly", response_model=MonthlyReport)
def monthly_totals(
    db: DbSession,
    user: CurrentUser,
    year: Annotated[int | None, Query(ge=2000, le=2100, description="Defaults to the current year")] = None,
) -> MonthlyReport:
    """For one calendar year: how much was spent in each month, split by category.

    One SQL query does the work (GROUP BY month and category), so the cost does not grow with the
    number of requests, only with the user's expenses in that year.
    """
    year = year or date.today().year
    month = extract("month", Expense.spent_at)
    total = func.sum(Expense.amount)
    rows = db.execute(
        select(month.label("month"), Expense.category, total.label("total"), func.count().label("count"))
        .where(
            Expense.user_id == user.id,
            # A range (not "year(spent_at) = ...") so the (user_id, spent_at) index can be used.
            Expense.spent_at >= date(year, 1, 1),
            Expense.spent_at < date(year + 1, 1, 1),
        )
        .group_by(month, Expense.category)
        .order_by(month, total.desc(), Expense.category)
    ).all()

    months: dict[int, MonthTotal] = {}
    for row in rows:
        m = int(row.month)
        if m not in months:
            months[m] = MonthTotal(month=f"{year}-{m:02d}", total=Decimal("0.00"), categories=[])
        months[m].categories.append(CategoryTotal(category=row.category, total=row.total, count=row.count))
        months[m].total += row.total

    ordered = [months[m] for m in sorted(months)]
    return MonthlyReport(
        year=year,
        grand_total=sum((m.total for m in ordered), Decimal("0.00")),
        months=ordered,
    )

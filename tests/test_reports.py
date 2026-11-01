from datetime import date
from decimal import Decimal

from tests.conftest import add_expense


def seed(client, headers):
    rows = [
        ("2026-01-05", "groceries", "10.10"),
        ("2026-01-20", "groceries", "20.20"),
        ("2026-01-31", "leisure", "5.00"),
        ("2026-03-01", "health", "99.99"),
        ("2026-03-15", "groceries", "0.10"),
        ("2026-03-15", "groceries", "0.20"),
        ("2026-12-31", "others", "1.00"),
        ("2025-12-31", "groceries", "500.00"),  # another year: never in the 2026 report
        ("2027-01-01", "groceries", "700.00"),  # another year: never in the 2026 report
    ]
    for spent_at, category, amount in rows:
        add_expense(client, headers, amount=amount, category=category, spent_at=spent_at)


def test_monthly_totals_per_category(client, alice):
    seed(client, alice)
    report = client.get("/reports/monthly?year=2026", headers=alice).json()
    assert report["year"] == 2026
    assert [m["month"] for m in report["months"]] == ["2026-01", "2026-03", "2026-12"]  # empty months omitted

    january, march, december = report["months"]
    assert january["total"] == "35.30"
    assert january["categories"] == [
        {"category": "groceries", "total": "30.30", "count": 2},
        {"category": "leisure", "total": "5.00", "count": 1},
    ]
    assert march["total"] == "100.29"
    assert march["categories"] == [
        {"category": "health", "total": "99.99", "count": 1},
        {"category": "groceries", "total": "0.30", "count": 2},  # 0.10 + 0.20 is exactly 0.30
    ]
    assert december["total"] == "1.00"
    assert report["grand_total"] == "136.59"


def test_categories_are_ordered_by_total_largest_first(client, alice):
    add_expense(client, alice, amount="1.00", category="health", spent_at="2026-05-01")
    add_expense(client, alice, amount="3.00", category="utilities", spent_at="2026-05-02")
    add_expense(client, alice, amount="2.00", category="leisure", spent_at="2026-05-03")
    categories = client.get("/reports/monthly?year=2026", headers=alice).json()["months"][0]["categories"]
    assert [c["category"] for c in categories] == ["utilities", "leisure", "health"]


def test_a_year_with_no_expenses_is_empty_not_an_error(client, alice):
    report = client.get("/reports/monthly?year=2031", headers=alice).json()
    assert report == {"year": 2031, "grand_total": "0.00", "months": []}


def test_year_defaults_to_the_current_year(client, alice):
    add_expense(client, alice, amount="4.00", spent_at=date.today())
    report = client.get("/reports/monthly", headers=alice).json()
    assert report["year"] == date.today().year and report["grand_total"] == "4.00"


def test_invalid_years_are_rejected(client, alice):
    for year in ("1999", "2101", "abc"):
        assert client.get(f"/reports/monthly?year={year}", headers=alice).status_code == 422


def test_report_only_counts_the_callers_expenses(client, alice, bob):
    seed(client, alice)
    add_expense(client, bob, amount="1000.00", category="groceries", spent_at="2026-01-05")
    alice_report = client.get("/reports/monthly?year=2026", headers=alice).json()
    assert alice_report["grand_total"] == "136.59"
    bob_report = client.get("/reports/monthly?year=2026", headers=bob).json()
    assert bob_report["grand_total"] == "1000.00"


def test_report_matches_a_plain_python_calculation(client, alice):
    """Cross-check the SQL against the simplest possible implementation, on many mixed rows."""
    import random

    rng = random.Random(7)
    categories = ["groceries", "leisure", "electronics", "utilities", "clothing", "health", "others"]
    expected: dict[tuple[str, str], Decimal] = {}
    for _ in range(150):
        spent_at = date(2026, rng.randint(1, 12), rng.randint(1, 28))
        category = rng.choice(categories)
        amount = Decimal(rng.randint(1, 50000)) / 100
        add_expense(client, alice, amount=str(amount), category=category, spent_at=spent_at)
        key = (f"{spent_at:%Y-%m}", category)
        expected[key] = expected.get(key, Decimal("0")) + amount

    report = client.get("/reports/monthly?year=2026", headers=alice).json()
    got = {(m["month"], c["category"]): Decimal(c["total"]) for m in report["months"] for c in m["categories"]}
    assert got == expected
    assert Decimal(report["grand_total"]) == sum(expected.values())
    for month in report["months"]:
        assert Decimal(month["total"]) == sum(Decimal(c["total"]) for c in month["categories"])

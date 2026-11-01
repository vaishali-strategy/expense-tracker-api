from datetime import date, timedelta

import pytest

from tests.conftest import add_expense

TODAY = date.today()


def days_ago(n):
    return TODAY - timedelta(days=n)


def ids(response):
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


@pytest.fixture
def seeded(client, alice):
    """Expenses at known distances from today (the amount encodes the age, to read failures easily)."""
    return {
        age: add_expense(client, alice, amount=f"{age + 1}.00", spent_at=days_ago(age), category=category)
        for age, category in [
            (0, "groceries"), (6, "leisure"), (7, "groceries"), (29, "health"), (30, "groceries"),
            (89, "utilities"), (90, "groceries"), (400, "others"),
        ]
    }


def test_no_filter_returns_everything_newest_first(client, alice, seeded):
    response = client.get("/expenses", headers=alice)
    assert ids(response) == [seeded[age]["id"] for age in (0, 6, 7, 29, 30, 89, 90, 400)]
    assert response.json()["total"] == 8


def test_period_week_is_the_last_7_days_including_today(client, alice, seeded):
    assert ids(client.get("/expenses?period=week", headers=alice)) == [seeded[0]["id"], seeded[6]["id"]]


def test_period_month_is_the_last_30_days_including_today(client, alice, seeded):
    got = ids(client.get("/expenses?period=month", headers=alice))
    assert got == [seeded[age]["id"] for age in (0, 6, 7, 29)]


def test_period_3months_is_the_last_90_days_including_today(client, alice, seeded):
    got = ids(client.get("/expenses?period=3months", headers=alice))
    assert got == [seeded[age]["id"] for age in (0, 6, 7, 29, 30, 89)]


def test_future_dated_expenses_are_not_in_a_period(client, alice):
    add_expense(client, alice, spent_at=TODAY + timedelta(days=3))
    assert client.get("/expenses?period=week", headers=alice).json()["total"] == 0
    assert client.get("/expenses", headers=alice).json()["total"] == 1


def test_custom_range_is_inclusive_at_both_ends(client, alice, seeded):
    start, end = days_ago(30), days_ago(7)
    got = ids(client.get(f"/expenses?start_date={start}&end_date={end}", headers=alice))
    assert got == [seeded[age]["id"] for age in (7, 29, 30)]


def test_start_date_alone_and_end_date_alone(client, alice, seeded):
    assert ids(client.get(f"/expenses?start_date={days_ago(7)}", headers=alice)) == [
        seeded[age]["id"] for age in (0, 6, 7)
    ]
    assert ids(client.get(f"/expenses?end_date={days_ago(89)}", headers=alice)) == [
        seeded[age]["id"] for age in (89, 90, 400)
    ]


def test_category_filter(client, alice, seeded):
    got = ids(client.get("/expenses?category=groceries", headers=alice))
    assert got == [seeded[age]["id"] for age in (0, 7, 30, 90)]


def test_category_and_period_combine(client, alice, seeded):
    got = ids(client.get("/expenses?category=groceries&period=month", headers=alice))
    assert got == [seeded[0]["id"], seeded[7]["id"]]


def test_period_cannot_be_combined_with_dates(client, alice):
    assert client.get(f"/expenses?period=week&start_date={TODAY}", headers=alice).status_code == 422
    assert client.get(f"/expenses?period=week&end_date={TODAY}", headers=alice).status_code == 422


@pytest.mark.parametrize(
    "query",
    ["period=year", "category=food", "start_date=nope", "limit=0", "limit=201", "offset=-1"],
)
def test_bad_query_values_are_rejected(client, alice, query):
    assert client.get(f"/expenses?{query}", headers=alice).status_code == 422


def test_end_before_start_is_rejected(client, alice):
    response = client.get(f"/expenses?start_date={TODAY}&end_date={days_ago(1)}", headers=alice)
    assert response.status_code == 422


def test_pagination(client, alice, seeded):
    first = client.get("/expenses?limit=3", headers=alice).json()
    assert first["total"] == 8 and first["limit"] == 3 and first["offset"] == 0 and len(first["items"]) == 3
    second = client.get("/expenses?limit=3&offset=3", headers=alice).json()
    third = client.get("/expenses?limit=3&offset=6", headers=alice).json()
    everything = first["items"] + second["items"] + third["items"]
    assert len(everything) == 8 and len({item["id"] for item in everything}) == 8  # no overlap, no gap
    assert client.get("/expenses?offset=100", headers=alice).json()["items"] == []


def test_same_day_expenses_have_a_stable_order(client, alice):
    first = add_expense(client, alice, spent_at=TODAY)
    second = add_expense(client, alice, spent_at=TODAY)
    assert ids(client.get("/expenses", headers=alice)) == [second["id"], first["id"]]


def test_filters_never_leak_another_users_rows(client, alice, bob):
    add_expense(client, alice, category="health", spent_at=TODAY)
    add_expense(client, bob, category="health", spent_at=TODAY)
    for query in ["", "?period=week", "?category=health", f"?start_date={TODAY}"]:
        assert client.get(f"/expenses{query}", headers=alice).json()["total"] == 1

from datetime import date

import pytest

from tests.conftest import add_expense


def test_create_returns_the_expense(client, alice):
    response = client.post(
        "/expenses",
        json={"amount": "12.50", "category": "groceries", "description": "milk", "spent_at": "2026-03-04"},
        headers=alice,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["amount"] == "12.50"  # money travels as a string, never a float
    assert body["category"] == "groceries"
    assert body["description"] == "milk"
    assert body["spent_at"] == "2026-03-04"
    assert isinstance(body["id"], int)


def test_spent_at_defaults_to_today_and_description_to_empty(client, alice):
    body = client.post("/expenses", json={"amount": "1", "category": "others"}, headers=alice).json()
    assert body["spent_at"] == str(date.today())
    assert body["description"] == ""
    assert body["amount"] == "1.00"


@pytest.mark.parametrize(
    "body",
    [
        {"amount": "0", "category": "groceries"},
        {"amount": "-5", "category": "groceries"},
        {"amount": "1.234", "category": "groceries"},  # more than 2 decimals
        {"amount": "1234567890123", "category": "groceries"},  # too many digits
        {"amount": "abc", "category": "groceries"},
        {"amount": "5", "category": "food"},  # not one of the seven categories
        {"amount": "5"},
        {"category": "groceries"},
        {"amount": "5", "category": "groceries", "spent_at": "yesterday"},
        {"amount": "5", "category": "groceries", "description": "x" * 201},
    ],
)
def test_create_validates_input(client, alice, body):
    assert client.post("/expenses", json=body, headers=alice).status_code == 422


def test_get_one(client, alice):
    created = add_expense(client, alice, amount="7.25", category="health")
    fetched = client.get(f"/expenses/{created['id']}", headers=alice)
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_get_missing_is_404(client, alice):
    assert client.get("/expenses/12345", headers=alice).status_code == 404


def test_patch_changes_only_the_fields_sent(client, alice):
    created = add_expense(client, alice, amount="10.00", category="groceries", description="old")
    response = client.patch(f"/expenses/{created['id']}", json={"amount": "11.50"}, headers=alice)
    assert response.status_code == 200
    updated = response.json()
    assert updated["amount"] == "11.50"
    assert updated["category"] == "groceries" and updated["description"] == "old"
    assert client.get(f"/expenses/{created['id']}", headers=alice).json() == updated


def test_patch_can_change_category_and_date(client, alice):
    created = add_expense(client, alice)
    updated = client.patch(
        f"/expenses/{created['id']}", json={"category": "leisure", "spent_at": "2025-01-02"}, headers=alice
    ).json()
    assert updated["category"] == "leisure" and updated["spent_at"] == "2025-01-02"


@pytest.mark.parametrize("body", [{}, {"amount": None}, {"amount": "0"}, {"category": "food"}])
def test_patch_validates_input(client, alice, body):
    created = add_expense(client, alice)
    assert client.patch(f"/expenses/{created['id']}", json=body, headers=alice).status_code == 422


def test_patch_missing_is_404(client, alice):
    assert client.patch("/expenses/999", json={"amount": "1"}, headers=alice).status_code == 404


def test_delete_then_gone(client, alice):
    created = add_expense(client, alice)
    assert client.delete(f"/expenses/{created['id']}", headers=alice).status_code == 204
    assert client.get(f"/expenses/{created['id']}", headers=alice).status_code == 404
    assert client.delete(f"/expenses/{created['id']}", headers=alice).status_code == 404


# ---- one user must never see or change another user's data ----


def test_other_users_expense_looks_like_it_does_not_exist(client, alice, bob):
    mine = add_expense(client, alice, amount="99.00")
    path = f"/expenses/{mine['id']}"
    assert client.get(path, headers=bob).status_code == 404
    assert client.patch(path, json={"amount": "1"}, headers=bob).status_code == 404
    assert client.delete(path, headers=bob).status_code == 404
    # and it is untouched
    assert client.get(path, headers=alice).json()["amount"] == "99.00"


def test_lists_only_contain_own_expenses(client, alice, bob):
    add_expense(client, alice, amount="1.00")
    add_expense(client, alice, amount="2.00")
    add_expense(client, bob, amount="3.00")
    assert client.get("/expenses", headers=alice).json()["total"] == 2
    bobs = client.get("/expenses", headers=bob).json()
    assert bobs["total"] == 1 and bobs["items"][0]["amount"] == "3.00"

"""The models and the migrations must describe the same database."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text

from app.db import engine
from app.models import Base


def test_models_match_the_migrations():
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)
    assert differences == []


def test_database_rejects_bad_rows_even_without_the_api(alice):
    """The rules also live in the database itself, so no code path can break them."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    insert = text(
        "INSERT INTO expenses (user_id, amount, category, description, spent_at) "
        "VALUES (1, :amount, :category, '', '2026-01-01')"
    )
    for amount, category in [(0, "groceries"), (-1, "groceries"), (5, "not-a-category")]:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(insert, {"amount": amount, "category": category})


def test_deleting_a_user_deletes_their_expenses(client, alice):
    client.post("/expenses", json={"amount": "5", "category": "others"}, headers=alice)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM users"))
        assert connection.execute(text("SELECT count(*) FROM expenses")).scalar_one() == 0

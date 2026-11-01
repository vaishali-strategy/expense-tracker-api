"""Test setup: a real PostgreSQL database, migrated from scratch once, emptied before every test."""

import os

# These must be set before the app is imported, because the app reads them at import time.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://expense:expense@localhost:5432/expense_test"
)
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hmac-sha256"
os.environ["APP_ENV"] = "test"
os.environ["BCRYPT_ROUNDS"] = "4"  # the minimum: keeps hashing fast in tests

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from expense_api.db import engine
from expense_api.main import app


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Start from an empty schema and build it with the real migrations (so they are tested too)."""
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def empty_tables():
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, expenses RESTART IDENTITY CASCADE"))


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


PASSWORD = "correct-horse-battery"


def register(client: TestClient, email: str = "alice@example.com") -> dict[str, str]:
    """Sign up and log in; returns the Authorization header for that user."""
    assert client.post("/auth/signup", json={"email": email, "password": PASSWORD}).status_code == 201
    token = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def alice(client):
    return register(client, "alice@example.com")


@pytest.fixture
def bob(client):
    return register(client, "bob@example.com")


def add_expense(client, headers, amount="10.00", category="groceries", spent_at=None, description=""):
    body = {"amount": amount, "category": category, "description": description}
    if spent_at is not None:
        body["spent_at"] = str(spent_at)
    response = client.post("/expenses", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()

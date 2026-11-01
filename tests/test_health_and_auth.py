from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from tests.conftest import PASSWORD, register


def test_health_is_ok(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_docs_page_exists(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_signup_returns_the_user_without_the_password(client):
    response = client.post("/auth/signup", json={"email": "Alice@Example.com", "password": PASSWORD})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"  # stored lower-case
    assert "password" not in body and "password_hash" not in body


def test_password_is_stored_hashed(client):
    client.post("/auth/signup", json={"email": "a@example.com", "password": PASSWORD})
    with engine.connect() as connection:
        stored = connection.execute(text("SELECT password_hash FROM users")).scalar_one()
    assert stored != PASSWORD and stored.startswith("$2")  # a bcrypt hash


def test_duplicate_email_is_rejected_whatever_the_case(client):
    assert client.post("/auth/signup", json={"email": "a@example.com", "password": PASSWORD}).status_code == 201
    again = client.post("/auth/signup", json={"email": "A@EXAMPLE.COM", "password": PASSWORD})
    assert again.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "password": PASSWORD},
        {"email": "a@example.com", "password": "short"},
        {"email": "a@example.com", "password": "x" * 65},
        {"email": "a@example.com"},
        {},
    ],
)
def test_signup_validates_input(client, body):
    assert client.post("/auth/signup", json=body).status_code == 422


def test_login_gives_a_token_that_works(client):
    headers = register(client)
    assert client.get("/expenses", headers=headers).status_code == 200


def test_wrong_password_and_unknown_email_look_the_same(client):
    client.post("/auth/signup", json={"email": "a@example.com", "password": PASSWORD})
    wrong = client.post("/auth/login", json={"email": "a@example.com", "password": "wrong-password"})
    unknown = client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


PROTECTED = [
    ("GET", "/expenses"),
    ("POST", "/expenses"),
    ("GET", "/expenses/1"),
    ("PATCH", "/expenses/1"),
    ("DELETE", "/expenses/1"),
    ("GET", "/reports/monthly"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_every_protected_endpoint_needs_a_token(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("method,path", PROTECTED)
def test_garbage_token_is_rejected(client, method, path):
    response = client.request(method, path, headers={"Authorization": "Bearer not.a.token"})
    assert response.status_code == 401


def _token(user_id, secret=None, expires_in=timedelta(minutes=5)):
    secret = secret or get_settings().secret_key
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + expires_in}, secret, algorithm="HS256"
    )


def test_expired_token_is_rejected(client, alice):
    expired = _token(1, expires_in=timedelta(minutes=-1))
    assert client.get("/expenses", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_token_signed_with_another_key_is_rejected(client, alice):
    forged = _token(1, secret="some-other-secret-that-is-also-long-enough-123456")
    assert client.get("/expenses", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_for_a_user_that_no_longer_exists_is_rejected(client):
    assert client.get("/expenses", headers={"Authorization": f"Bearer {_token(999)}"}).status_code == 401


def test_production_refuses_to_start_with_the_default_secret(monkeypatch):
    from fastapi.testclient import TestClient

    from app import main
    from app.config import DEFAULT_SECRET, Settings

    monkeypatch.setattr(main, "get_settings", lambda: Settings(app_env="production", secret_key=DEFAULT_SECRET))
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        with TestClient(main.app):
            pass

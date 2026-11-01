"""Password hashing and JSON Web Tokens."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from expense_api.config import get_settings

ALGORITHM = "HS256"

# A real bcrypt hash of a random password. Login checks a password against it when the email is
# unknown, so "no such user" takes as long as "wrong password" (no timing hint about which
# emails exist).
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    """True if the password matches. With no hash (unknown user) it still does the work, then says no."""
    matches = bcrypt.checkpw(password.encode(), (password_hash or _DUMMY_HASH).encode())
    return matches and password_hash is not None


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expires}, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """The user id inside a valid, unexpired token, or None."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None

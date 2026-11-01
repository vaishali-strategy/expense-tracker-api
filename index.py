"""Entry point for Vercel: it looks for a FastAPI object called `app` in this module
(see [tool.vercel] in pyproject.toml). Running locally uses app.main:app directly."""

from app.main import app  # noqa: F401

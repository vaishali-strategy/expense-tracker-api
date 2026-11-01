"""Entry point for Vercel: it looks for a FastAPI object called `app` in this module
(a root-level index.py is one of the file names Vercel looks for). Running locally uses expense_api.main:app directly."""

from expense_api.main import app  # noqa: F401

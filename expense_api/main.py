"""The FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from expense_api.config import DEFAULT_SECRET, get_settings
from expense_api.db import engine
from expense_api.routers import auth, expenses, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.app_env == "production" and settings.secret_key == DEFAULT_SECRET:
        raise RuntimeError("Set SECRET_KEY before running in production")
    yield


app = FastAPI(
    title="Expense Tracker API",
    version="1.0.0",
    description="Sign up, log in, track your own expenses, filter them, and see monthly totals per category.",
    lifespan=lifespan,
)
app.include_router(auth.router)
app.include_router(expenses.router)
app.include_router(reports.router)


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """200 when the app can reach its database, 503 otherwise."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")
    return {"status": "ok"}

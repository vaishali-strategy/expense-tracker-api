"""Database engine and the per-request session."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# prepare_threshold=None: do not use server-side prepared statements, so the app also works behind
# a connection pooler (such as the "pooled" connection strings some hosts offer).
engine = create_engine(
    get_settings().database_url, pool_pre_ping=True, connect_args={"prepare_threshold": None}
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session

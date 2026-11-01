"""Database engine and the per-request session."""

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from expense_api.config import get_settings

# prepare_threshold=None: do not use server-side prepared statements, so the app also works behind
# a connection pooler (such as the "pooled" connection strings some hosts offer).
#
# On Vercel the app runs as short-lived serverless functions, so a connection pool inside each one
# would only pile up connections. There, open a connection per request and let the database
# provider's pooler do the pooling (Vercel sets the VERCEL environment variable).
if os.environ.get("VERCEL"):
    engine_options = {"poolclass": NullPool}
else:
    engine_options = {"pool_pre_ping": True}

engine = create_engine(
    get_settings().database_url, connect_args={"prepare_threshold": None}, **engine_options
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session

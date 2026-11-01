#!/bin/sh
# Container entry point: bring the database schema up to date, then start the API.
set -e
alembic upgrade head
exec uvicorn expense_api.main:app --host 0.0.0.0 --port "${PORT:-8000}"

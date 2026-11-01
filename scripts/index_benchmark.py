"""Measure what the (user_id, spent_at) index buys.

Fills the database with 1,000,000 expenses spread over 1,000 users, runs the two queries the API
depends on with and without the index, and prints the database's own execution time (the median of
5 runs of EXPLAIN ANALYZE). Everything it creates is deleted at the end.

    python scripts/index_benchmark.py            # uses DATABASE_URL (default: the dev database)
"""

import json
import statistics
import sys
from datetime import date

from sqlalchemy import create_engine, text

sys.path.insert(0, ".")
from app.config import get_settings  # noqa: E402

USERS, PER_USER, RUNS = 1000, 1000, 5

LIST_QUERY = """
    SELECT * FROM expenses
    WHERE user_id = :uid AND spent_at >= :start AND spent_at <= :end
    ORDER BY spent_at DESC, id DESC LIMIT 50
"""
REPORT_QUERY = """
    SELECT extract(month FROM spent_at) AS m, category, sum(amount), count(*)
    FROM expenses
    WHERE user_id = :uid AND spent_at >= :start AND spent_at < :next_year
    GROUP BY m, category ORDER BY m
"""


def run_ms(connection, sql, params) -> float:
    plan = connection.execute(text("EXPLAIN (ANALYZE, FORMAT JSON) " + sql), params).scalar_one()
    plan = plan if isinstance(plan, list) else json.loads(plan)
    return plan[0]["Execution Time"]


def median_ms(connection, sql, params) -> float:
    return statistics.median(run_ms(connection, sql, params) for _ in range(RUNS))


def main() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.begin() as connection:
        print(f"Seeding {USERS * PER_USER:,} expenses...")
        connection.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "SELECT 'bench-' || g || '@example.com', 'x' FROM generate_series(1, :n) g"
            ),
            {"n": USERS},
        )
        connection.execute(
            text(
                """
                INSERT INTO expenses (user_id, amount, category, description, spent_at)
                SELECT u.id,
                       round((random() * 200 + 1)::numeric, 2),
                       (ARRAY['groceries','leisure','electronics','utilities','clothing','health','others'])[1 + floor(random() * 7)::int],
                       '',
                       DATE '2026-01-01' - (random() * 1095)::int
                FROM users u, generate_series(1, :per) g
                WHERE u.email LIKE 'bench-%'
                """
            ),
            {"per": PER_USER},
        )
        connection.execute(text("ANALYZE expenses"))

    try:
        with engine.connect() as connection:
            uid = connection.execute(text("SELECT id FROM users WHERE email LIKE 'bench-%' ORDER BY id LIMIT 1 OFFSET 500")).scalar_one()
            rows = connection.execute(text("SELECT count(*) FROM expenses")).scalar_one()
            list_params = {"uid": uid, "start": date(2025, 1, 1), "end": date(2025, 12, 31)}
            report_params = {"uid": uid, "start": date(2025, 1, 1), "next_year": date(2026, 1, 1)}
            print(f"{rows:,} rows in the table; timing one user's queries (median of {RUNS} runs)\n")

            results = {}
            for label, drop_index in (("with the index", False), ("without the index", True)):
                if drop_index:  # DDL is transactional in PostgreSQL, so the rollback below restores it
                    connection.execute(text("DROP INDEX ix_expenses_user_spent"))
                results[label] = (
                    median_ms(connection, LIST_QUERY, list_params),
                    median_ms(connection, REPORT_QUERY, report_params),
                )
                connection.rollback()

        print(f"{'':22}{'list (1 year, 50 rows)':>24}{'report (monthly totals)':>26}")
        for label, (list_ms, report_ms) in results.items():
            print(f"{label:22}{list_ms:>21.2f} ms{report_ms:>23.2f} ms")
        with_index, without = results["with the index"], results["without the index"]
        print(f"\nspeed-up: list {without[0] / with_index[0]:.0f}x, report {without[1] / with_index[1]:.0f}x")
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM users WHERE email LIKE 'bench-%'"))
        print("(benchmark data removed)")


if __name__ == "__main__":
    main()

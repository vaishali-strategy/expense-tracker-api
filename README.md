# Expense Tracker API

![CI](https://github.com/vaishali-strategy/expense-tracker-api/actions/workflows/ci.yml/badge.svg)

A small REST API for tracking personal expenses. A user signs up, logs in, records expenses, filters
them by date range and category, and asks for **monthly totals per category**. Built with FastAPI and
PostgreSQL, covered by an automated test suite that runs against a real database.

**Live demo:** _add your URL here after the first deploy (see [Deploy](#deploy-a-live-url))_
&nbsp;·&nbsp; interactive docs at `/docs`

## What it does

| Method and path | What it does |
|---|---|
| `POST /auth/signup` | create an account (`email`, `password`) |
| `POST /auth/login` | get a JWT access token |
| `POST /expenses` | add an expense (`amount`, `category`, `description`, `spent_at`) |
| `GET /expenses` | list your expenses, newest first, with filters (below) |
| `GET /expenses/{id}` | one expense |
| `PATCH /expenses/{id}` | change some fields of an expense |
| `DELETE /expenses/{id}` | delete an expense |
| `GET /reports/monthly?year=2026` | total spent per month, split by category |
| `GET /health` | 200 if the app can reach its database |

**Categories** (fixed): `groceries`, `leisure`, `electronics`, `utilities`, `clothing`, `health`, `others`.

**Filters on `GET /expenses`** (all optional, combinable):

- `period=week|month|3months`: the last 7, 30 or 90 days, including today
- `start_date` and `end_date`: a custom range, both ends inclusive (cannot be combined with `period`)
- `category=groceries`
- `limit` (1 to 200, default 50) and `offset` for paging; the response includes `total`

Every endpoint except `signup`, `login` and `health` needs `Authorization: Bearer <token>`.
Each user can only ever see and change their own expenses.

## Try it in two minutes

```bash
docker compose up --build        # API on http://localhost:8000 and a PostgreSQL database
```

Open **http://localhost:8000/docs**, then: `POST /auth/signup`, `POST /auth/login`, copy the
`access_token`, click **Authorize** and paste it. Every endpoint can then be tried from the page.

### Or with curl

```bash
B=http://localhost:8000
curl -s -X POST $B/auth/signup -H 'Content-Type: application/json' \
     -d '{"email":"demo@example.com","password":"correct-horse-battery"}'
TOKEN=$(curl -s -X POST $B/auth/login -H 'Content-Type: application/json' \
     -d '{"email":"demo@example.com","password":"correct-horse-battery"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X POST $B/expenses -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"amount":"54.20","category":"groceries","description":"weekly shop","spent_at":"2026-10-03"}'

curl -s "$B/expenses?category=groceries&limit=2" -H "Authorization: Bearer $TOKEN"
curl -s "$B/reports/monthly?year=2026" -H "Authorization: Bearer $TOKEN"
```

A real response from `/reports/monthly?year=2026` (months with no expenses are left out; categories
are sorted largest first):

```json
{
  "year": 2026,
  "grand_total": "212.49",
  "months": [
    { "month": "2026-09", "total": "24.50",
      "categories": [ { "category": "health", "total": "24.50", "count": 1 } ] },
    { "month": "2026-10", "total": "98.99",
      "categories": [ { "category": "groceries", "total": "86.00", "count": 2 },
                      { "category": "leisure",   "total": "12.99", "count": 1 } ] },
    { "month": "2026-11", "total": "89.00",
      "categories": [ { "category": "utilities", "total": "89.00", "count": 1 } ] }
  ]
}
```

## Run it without Docker

You need Python 3.13 and a PostgreSQL server.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

createdb expense_dev                      # or any database you like
cp .env.example .env                      # then edit DATABASE_URL and SECRET_KEY
alembic upgrade head                      # create the tables
uvicorn app.main:app --reload             # http://localhost:8000/docs
```

## Design decisions

| Decision | Why |
|---|---|
| **PostgreSQL, with Alembic migrations** | The schema is versioned in code, and the tests build the database from the same migrations the deploy uses. |
| **Money is `NUMERIC(12,2)` and travels as a string** (`"12.50"`) | Floating point cannot represent 0.10 + 0.20 exactly; a decimal type can. A test checks that it adds up to exactly `0.30`. |
| **Rules live in the database too** (`amount > 0`, category must be one of seven, foreign key with `ON DELETE CASCADE`) | The API validates input, but a bug or a manual SQL statement still cannot create a bad row. A test inserts bad rows directly. |
| **Someone else's expense returns 404, not 403** | A 403 would confirm that the id exists. |
| **Login gives one answer for "no such email" and "wrong password"**, and does the same hashing work in both cases | Prevents learning which emails are registered, by message or by response time. |
| **Passwords hashed with bcrypt; tokens are signed JWTs that expire** | Standard, and each has a test (plain text is never stored; forged, expired and garbage tokens are refused). |
| **The report is one SQL query** (`GROUP BY month, category`) with a date *range*, not `year(spent_at) = 2026` | One round trip, and the range lets the index be used. |
| **Production refuses to start with the default `SECRET_KEY`** | A forgotten secret should be a loud error, not a silent security hole. |
| **Synchronous SQLAlchemy** | Simpler to read and enough for this API; async would add complexity without a benefit here. |

## Tests

```bash
createdb expense_test                     # once
python -m pytest -q                       # 84 tests, about 4 seconds
```

The tests run against a real PostgreSQL database (`TEST_DATABASE_URL`, default
`postgresql+psycopg://expense:expense@localhost:5432/expense_test`). Before the suite starts, the
schema is dropped and rebuilt from the migrations; each test starts with empty tables. They cover:

- **Auth:** signup, duplicate and mixed-case emails, input validation, hashing, wrong password and unknown
  email, and every protected endpoint against missing, garbage, expired, forged and orphaned tokens.
- **Expenses:** create, read, partial update, delete, every kind of invalid input, and that one user can
  never read, change, delete or list another user's data.
- **Filters:** the exact edges of `week`, `month` and `3months`, inclusive custom ranges, category, paging
  without gaps or overlaps, and filters never leaking another user's rows.
- **Reports:** hand-computed totals, ordering, other years excluded, exact decimal sums, and a cross-check
  of the SQL against a plain Python calculation on 150 random rows.
- **Database:** the models match the migrations (no drift), the database rejects bad rows, deleting a user
  deletes their expenses.

To check the tests themselves, I planted twelve bugs one at a time (an owner check removed, a period off by a
day, an inclusive range made exclusive, plain-text passwords, tokens that never expire, a report that includes
next January, and so on). Eleven made a test fail. The twelfth, removing the explicit "email already
registered" check, correctly changes nothing, because the database's unique constraint still answers 409.

CI (`.github/workflows/ci.yml`) runs the same suite on every push, against a PostgreSQL service container.

## What the index buys

Every list and report query filters by user and a date range, so the table has an index on
`(user_id, spent_at)`. `scripts/index_benchmark.py` measures it: it inserts 1,000,000 expenses over 1,000
users, takes one user's queries, and compares PostgreSQL's own `EXPLAIN ANALYZE` execution time with and
without the index (median of 5 runs; all test data is deleted afterwards).

Apple M2, PostgreSQL 18 running locally, three runs of the script:

| Query | With the index | Without the index | Speed-up |
|---|---|---|---|
| List one user's expenses for a year (50 rows) | about 0.02 ms | 26 to 33 ms | roughly 1,100x to 1,600x |
| Monthly totals per category for a year | 0.27 to 0.32 ms | 25 to 33 ms | roughly 90x to 120x |

Without the index PostgreSQL reads all 1,000,000 rows to find one user's; with it, it jumps straight to
them. These are local numbers for one table size, not a promise about any other setup. Run it yourself:
`python scripts/index_benchmark.py`.

## Deploy a live URL

The app runs on **Vercel's free Hobby plan** and the database is a **free Neon PostgreSQL**. Neither needs a
payment card as far as their docs describe (check at signup; if either asks for one, stop). Vercel's Hobby
plan is for personal, non-commercial use, which a portfolio project is. Neon's free projects are not paused
or deleted for inactivity.

1. **Database.** Create a project at [neon.com](https://neon.com). Copy the **pooled** connection string (the
   host contains `-pooler`; it starts with `postgresql://` and ends with `?sslmode=require`).
2. **Create the tables, once, from your laptop** (the venv from "Run it without Docker" active):
   ```bash
   DATABASE_URL='<paste the Neon string>' alembic upgrade head
   ```
3. **Code.** Push this repository to GitHub.
4. **App.** On [vercel.com](https://vercel.com), sign in with GitHub, choose **Add New, Project**, and import the
   repository. Vercel detects FastAPI by itself (`index.py` and `pyproject.toml` tell it where the app is).
   Under **Environment Variables** add:

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the Neon string |
   | `SECRET_KEY` | a long random string: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `APP_ENV` | `production` |

   Click **Deploy**.
5. **Check it.** Open `https://<your-project>.vercel.app/health` (should say `{"status":"ok"}`) and `/docs`
   **in a private browser window**. If it asks you to log in to Vercel, open the project's **Settings, then
   Deployment Protection** and turn Vercel Authentication off for production. Then put the URL at the top of
   this README and on your resume.

Notes:

- The API runs as serverless functions, so the first request after a quiet period is slower. The database
  also suspends after a few idle minutes and wakes on the next query. Open the link yourself shortly before
  sharing it.
- On Vercel the app opens a database connection per request and relies on Neon's pooler (the code switches
  its own pool off when the `VERCEL` variable is set).
- When the schema changes, run `alembic upgrade head` against the Neon string again before deploying.
- `docker compose up --build` remains the way to run everything locally, and the `Dockerfile` works on any
  host that runs containers.

## Project layout

```
app/
  main.py          the FastAPI app, /health, startup check
  config.py        settings from environment variables
  db.py            database engine and per-request session
  models.py        users and expenses tables (with their constraints and index)
  schemas.py       what the API accepts and returns
  security.py      password hashing and JWT
  deps.py          "who is calling?" (the current user)
  routers/         auth.py, expenses.py, reports.py
alembic/           database migrations (run with `alembic upgrade head`)
tests/             84 tests against a real PostgreSQL
scripts/           index_benchmark.py
index.py           entry point Vercel uses (re-exports the app)
Dockerfile  docker-compose.yml  start.sh  .github/workflows/ci.yml  .vercelignore
```

## Limits (deliberately simple)

No refresh tokens, no password reset or email verification, no rate limiting, no per-user custom categories,
and one currency. Each would be a sensible next step; none is needed to show the data model, authentication,
filtering and reporting working correctly.

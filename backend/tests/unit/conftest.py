"""Shared setup for the offline unit suite.

These tests run against a local Postgres and never touch the network, unlike
tests/backend_test.py which drives a deployed instance over HTTP. Run them
with (from the backend/ directory, with a local Postgres reachable):

    pytest tests/unit

Everything goes through a single `client` fixture. asyncpg pools are bound to
the event loop they were created in, and FastAPI's TestClient only runs the
app's startup/shutdown lifespan (which is what creates the pool) while used
as a context manager, each entry getting its own loop via `client.portal`.
Two independent asyncio.run() calls in the same test would each try to touch
that pool from a different loop and fail — so instead of a bare `run(coro)`
helper, every async call in a test (whether it hits an HTTP route or reaches
the database directly) goes through `client.portal.call(fn, *args)`, which
runs `fn` inside the exact loop the app's pool lives in.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

# pytest.ini pins this suite to `-n 2 --dist loadscope`: two worker PROCESSES,
# each running whole modules sequentially. A single shared Postgres database
# doesn't give that the isolation mongomock used to (each worker got its own
# in-memory instance for free) — two workers clearing tables concurrently
# against the same database wipe rows out from under each other's in-flight
# test. So each worker gets its own database, named after pytest-xdist's own
# worker id, created and migrated once before any test runs.
_BASE_DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost/fantm_test")
_WORKER_ID = os.environ.get("PYTEST_XDIST_WORKER", "master")
_TEST_DB_NAME = f"fantm_test_{_WORKER_ID}"
_SCHEMA_SQL = (BACKEND_DIR / "migrations" / "001_fantm_schema.sql").read_text()


def _with_db_name(url: str, db_name: str) -> str:
    return f"{url.rsplit('/', 1)[0]}/{db_name}"


async def _ensure_worker_database():
    import asyncpg
    admin_conn = await asyncpg.connect(_with_db_name(_BASE_DB_URL, "postgres"))
    try:
        exists = await admin_conn.fetchval("select 1 from pg_database where datname = $1", _TEST_DB_NAME)
        if not exists:
            await admin_conn.execute(f'create database "{_TEST_DB_NAME}"')
    finally:
        await admin_conn.close()

    schema_conn = await asyncpg.connect(_with_db_name(_BASE_DB_URL, _TEST_DB_NAME))
    try:
        await schema_conn.execute(_SCHEMA_SQL)
    finally:
        await schema_conn.close()


asyncio.run(_ensure_worker_database())

os.environ["DATABASE_URL"] = _with_db_name(_BASE_DB_URL, _TEST_DB_NAME)
os.environ.setdefault("JWT_SECRET", "t" * 48)
os.environ.setdefault("GROQ_API_KEY", "gsk_test")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test")
os.environ.setdefault("CORS_ORIGINS", "https://fantm.ink")

import auth, books, credits, generation, payments, pricing  # noqa: E402,F401
import db as db_module  # noqa: E402
from server import app  # noqa: E402 — the real app: its startup/shutdown events
# are what create and tear down the asyncpg pool. A hand-built FastAPI() with
# just the routers included skips that lifecycle, so a pool created lazily by
# the first test leaks past its own event loop's lifetime — every subsequent
# test's portal then hands that pool a loop it wasn't created on, and asyncpg
# refuses with "attached to a different loop".

# Child-to-parent, so foreign keys never block a delete.
TABLES_IN_FK_ORDER = ("login_attempts", "credit_transactions", "payment_transactions", "chapters", "books", "users")


async def _clear_tables():
    pool = await db_module.get_pool()
    for name in TABLES_IN_FK_ORDER:
        await pool.execute(f"delete from {name}")


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.portal.call(_clear_tables)
        yield c


@pytest.fixture
def db(client):
    """Proxy for reaching the database (or any other async call) from a test
    body in the same loop `client` is using: db.call(fn, *args) runs
    `await fn(*args)` inside the app's own event loop."""
    class _DB:
        @staticmethod
        def call(fn, *args):
            return client.portal.call(fn, *args)
    return _DB()


def cookies_for(user_id, email="user@fantm.ink"):
    return {"access_token": auth.create_access_token(str(user_id), email)}

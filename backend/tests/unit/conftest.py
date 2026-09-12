"""Shared setup for the offline unit suite.

These tests run against an in-memory Mongo and never touch the network, unlike
tests/backend_test.py which drives a deployed instance over HTTP. Run them with:

    pytest backend/tests/unit

The environment and the database handle are both installed here, before any
backend module is imported: every module reads its config at import time and
binds `db` with `from db import db`, so the substitution has to happen first.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "fantm_test")
os.environ.setdefault("JWT_SECRET", "t" * 48)
os.environ.setdefault("GROQ_API_KEY", "gsk_test")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test")
os.environ.setdefault("CORS_ORIGINS", "https://fantm.ink")

from mongomock_motor import AsyncMongoMockClient  # noqa: E402

MOCK_DB = AsyncMongoMockClient()["fantm_test"]

import db as db_module  # noqa: E402
db_module.db = MOCK_DB

import credits, deps, auth, books, payments, generation, pricing  # noqa: E402,F401
for _module in (credits, deps, auth, books, payments):
    _module.db = MOCK_DB

COLLECTIONS = ("users", "books", "chapters", "credit_transactions", "payment_transactions", "login_attempts")


def run(coro):
    """Drive one coroutine to completion. The suite is deliberately synchronous
    so each test controls exactly when the database is read."""
    return asyncio.run(coro)


@pytest.fixture
def db():
    async def clear():
        for name in COLLECTIONS:
            await MOCK_DB[name].delete_many({})
        return MOCK_DB
    return run(clear())


@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(books.router)
    app.include_router(payments.router)
    return TestClient(app)


def cookies_for(user_id, email="user@fantm.ink"):
    return {"access_token": auth.create_access_token(str(user_id), email)}

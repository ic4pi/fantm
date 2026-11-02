import json
import logging
import os
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

DATABASE_URL = os.environ["DATABASE_URL"]

pool: asyncpg.Pool | None = None


async def _init_connection(conn: asyncpg.Connection):
    # jsonb/json columns hold lists/dicts (characters, plot_threads, outline) —
    # decode/encode them transparently so call sites pass and receive plain
    # Python objects, same as they did with Mongo's native document types.
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog", format="text")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog", format="text")


async def connect() -> asyncpg.Pool:
    """Open the pool and bring the schema up to date. Raises if the database
    is unreachable; the next get_pool() call simply tries again, so the app
    recovers on its own once the database is back."""
    global pool
    if pool is None:
        new_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10, init=_init_connection)
        if pool is None:
            pool = new_pool
            await apply_migrations()
        else:
            # Two first requests raced to connect; keep the one that won.
            await new_pool.close()
    return pool


async def get_pool() -> asyncpg.Pool:
    """Lazily connect — lets tests and scripts use the db without duplicating
    the startup call server.py makes for the running app."""
    return pool if pool is not None else await connect()


async def disconnect():
    global pool
    if pool is not None:
        await pool.close()
        pool = None


async def apply_migrations():
    """Run every migrations/*.sql in order. Each one is written to be
    idempotent (if not exists), so this is safe on every boot, and a deploy
    whose code needs a new column can't go live ahead of that column. A file
    that fails (e.g. a role without permission to create an extension) is
    logged and skipped rather than blocking the ones after it."""
    pool = await get_pool()
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        try:
            await pool.execute(path.read_text())
        except Exception:
            logger.exception("Migration %s failed", path.name)

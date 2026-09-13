import json
import os

import asyncpg

DATABASE_URL = os.environ["DATABASE_URL"]

pool: asyncpg.Pool | None = None


async def _init_connection(conn: asyncpg.Connection):
    # jsonb/json columns hold lists/dicts (characters, plot_threads, outline) —
    # decode/encode them transparently so call sites pass and receive plain
    # Python objects, same as they did with Mongo's native document types.
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog", format="text")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog", format="text")


async def connect() -> asyncpg.Pool:
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10, init=_init_connection)
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

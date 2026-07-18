"""Postgres access: a shared asyncpg pool + idempotent schema init.

pgvector's `register_vector` teaches asyncpg how to send/receive `vector` columns
as Python lists — so we can pass an embedding straight into a query parameter.
It requires the `vector` extension to already exist, so `init_schema()` (which runs
`CREATE EXTENSION`) must run once before the pool is used.
"""
from pathlib import Path

import asyncpg
from pgvector.asyncpg import register_vector

from app.config import settings

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"
_pool: asyncpg.Pool | None = None


async def init_schema() -> None:
    """Create the extension + tables + indexes (idempotent). Uses a one-off connection."""
    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute(_SCHEMA_PATH.read_text())
    finally:
        await conn.close()


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=5,
            init=register_vector,  # register the vector codec on every connection
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None

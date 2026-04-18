import sqlite3
from collections.abc import Iterator

import pytest

from locontext.store.sqlite import SQLiteStore


@pytest.fixture()
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture()
def store(connection: sqlite3.Connection) -> SQLiteStore:
    store = SQLiteStore(connection)
    store.ensure_schema()
    return store

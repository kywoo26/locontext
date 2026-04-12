from __future__ import annotations

import sqlite3
from importlib import import_module
from typing import Protocol, cast

from ..domain.contracts import QueryEngine
from ..domain.models import QueryHit
from ..store.sqlite import SQLiteStore


class _QueryEngineFactory(Protocol):
    def __call__(self, connection: sqlite3.Connection) -> QueryEngine: ...


class _EngineModule(Protocol):
    SQLiteLexicalEngine: _QueryEngineFactory


def query_local(store: SQLiteStore, text: str, *, limit: int) -> list[QueryHit]:
    module = cast(
        _EngineModule,
        cast(object, import_module("locontext.engine.sqlite_lexical")),
    )
    engine = module.SQLiteLexicalEngine(store.connection)
    return list(engine.query(text, limit=limit))

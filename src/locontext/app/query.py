from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from importlib import import_module
from typing import Protocol, cast

from ..domain.contracts import QueryEngine, QueryEngineDescriptor
from ..domain.models import QueryHit
from ..store.sqlite import SQLiteStore


class _QueryEngineFactory(Protocol):
    def __call__(self, connection: sqlite3.Connection) -> QueryEngine: ...


class _EngineModule(Protocol):
    SQLiteLexicalEngine: _QueryEngineFactory


@dataclass(slots=True)
class QueryResultHit:
    rank: int
    source_id: str
    source_locator: str
    snapshot_id: str
    document_id: str
    document_locator: str
    chunk_id: str
    chunk_index: int
    score: float
    matched_terms: list[str]
    match_query: str
    section_path: list[str]
    snippet: str
    text: str
    metadata: dict[str, object]


@dataclass(slots=True)
class QueryResultEnvelope:
    query_text: str
    limit: int
    source_id: str | None
    hit_count: int
    hits: list[QueryResultHit]

    def as_dict(self) -> dict[str, object]:
        return {
            "query": {
                "text": self.query_text,
                "limit": self.limit,
                "source_id": self.source_id,
            },
            "hit_count": self.hit_count,
            "hits": [asdict(hit) for hit in self.hits],
        }


def describe_local_query_engine(store: SQLiteStore) -> QueryEngineDescriptor:
    engine = _load_query_engine(store)
    describe = getattr(engine, "describe", None)
    if callable(describe):
        return cast(QueryEngineDescriptor, describe())
    return _baseline_descriptor_for(engine)


def query_local(
    store: SQLiteStore,
    text: str,
    *,
    limit: int,
    source_id: str | None = None,
) -> list[QueryHit]:
    engine = _load_query_engine(store)
    return list(engine.query(text, limit=limit, source_id=source_id))


def query_local_json(
    store: SQLiteStore,
    text: str,
    *,
    limit: int,
    source_id: str | None = None,
) -> QueryResultEnvelope:
    hits = query_local(store, text, limit=limit, source_id=source_id)
    query_terms = [term for term in text.split() if term]
    match_query = _build_match_query(query_terms)
    source_cache: dict[str, str] = {}
    document_cache: dict[str, dict[str, str]] = {}
    result_hits: list[QueryResultHit] = []

    for rank, hit in enumerate(hits, start=1):
        if hit.source_id not in source_cache:
            source = store.get_source(hit.source_id)
            source_cache[hit.source_id] = (
                source.canonical_locator if source is not None else hit.source_id
            )
        if hit.snapshot_id not in document_cache:
            document_cache[hit.snapshot_id] = {
                document.document_id: document.canonical_locator
                for document in store.list_documents(hit.snapshot_id)
            }
        section_path = hit.metadata.get("section_path")
        if isinstance(section_path, list):
            section_list = [str(part) for part in cast(list[object], section_path)]
        else:
            section_list = []
        result_hits.append(
            QueryResultHit(
                rank=rank,
                source_id=hit.source_id,
                source_locator=source_cache[hit.source_id],
                snapshot_id=hit.snapshot_id,
                document_id=hit.document_id,
                document_locator=document_cache.get(hit.snapshot_id, {}).get(
                    hit.document_id, hit.document_id
                ),
                chunk_id=hit.chunk_id,
                chunk_index=hit.chunk_index,
                score=hit.score,
                matched_terms=_matched_terms(hit.text, query_terms),
                match_query=match_query,
                section_path=section_list,
                snippet=_build_snippet(hit.text, text),
                text=hit.text,
                metadata=hit.metadata,
            )
        )

    return QueryResultEnvelope(
        query_text=text,
        limit=limit,
        source_id=source_id,
        hit_count=len(result_hits),
        hits=result_hits,
    )


def _build_snippet(text: str, query_text: str, *, max_chars: int = 160) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    terms = [term for term in query_text.split() if term]
    lower = normalized.lower()
    start = 0
    for term in terms:
        index = lower.find(term.lower())
        if index != -1:
            start = max(index - 20, 0)
            break
    end = min(start + max_chars, len(normalized))
    snippet = normalized[start:end].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(normalized):
        snippet = f"{snippet}..."
    return snippet


def _matched_terms(text: str, query_terms: list[str]) -> list[str]:
    lower = text.lower()
    return [term for term in query_terms if term.lower() in lower]


def _build_match_query(query_terms: list[str]) -> str:
    return " AND ".join(f'"{term}"' for term in query_terms)


def _load_query_engine(store: SQLiteStore) -> QueryEngine:
    module = cast(
        _EngineModule,
        cast(object, import_module("locontext.engine.sqlite_lexical")),
    )
    return module.SQLiteLexicalEngine(store.connection)


def _baseline_descriptor_for(engine: QueryEngine) -> QueryEngineDescriptor:
    engine_type = type(engine)
    if (
        engine_type.__module__ == "locontext.engine.sqlite_lexical"
        and engine_type.__name__ == "SQLiteLexicalEngine"
    ):
        return QueryEngineDescriptor(
            engine_kind="lexical",
            engine_name="sqlite_lexical",
            semantic_ready=False,
            is_baseline=True,
        )
    msg = f"query engine {engine_type.__module__}.{engine_type.__name__} must define describe()"
    raise TypeError(msg)

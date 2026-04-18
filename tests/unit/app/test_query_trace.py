import sqlite3
from importlib import import_module
from typing import Protocol, cast

from locontext.domain.models import (
    Chunk,
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


class _TraceHit(Protocol):
    rank: int
    source_locator: str
    document_locator: str
    section_path: list[str]
    metadata: dict[str, object]
    matched_terms: list[str]
    match_query: str


class _TraceEnvelope(Protocol):
    hits: list[_TraceHit]


class _QueryLocalJson(Protocol):
    def __call__(
        self, store: SQLiteStore, text: str, *, limit: int
    ) -> _TraceEnvelope: ...


class TestQueryTraceContract:
    def _seed_query_state(self) -> SQLiteStore:
        connection = sqlite3.connect(":memory:")
        store = SQLiteStore(connection)
        store.ensure_schema()
        source = Source(
            source_id="source-1",
            source_kind=SourceKind.WEB,
            requested_locator="https://docs.example.com/docs",
            resolved_locator="https://docs.example.com/docs",
            canonical_locator="https://docs.example.com/docs",
            docset_root="https://docs.example.com/docs",
        )
        store.upsert_source(source)
        snapshot = Snapshot(
            snapshot_id="snapshot-active",
            source_id=source.source_id,
            status=SnapshotStatus.INDEXED,
            content_hash="hash-active",
            is_active=True,
        )
        store.insert_snapshot(snapshot)
        documents = store.replace_snapshot_documents(
            snapshot.snapshot_id,
            source.source_id,
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/guide",
                    resolved_locator="https://docs.example.com/docs/guide",
                    canonical_locator="https://docs.example.com/docs/guide",
                    title="Guide",
                    content_hash="doc-hash-active",
                ),
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/reference",
                    resolved_locator="https://docs.example.com/docs/reference",
                    canonical_locator="https://docs.example.com/docs/reference",
                    title="Reference",
                    content_hash="doc-hash-reference",
                ),
            ],
        )
        store.replace_snapshot_chunks(
            snapshot.snapshot_id,
            [
                Chunk(
                    chunk_id=f"{documents[0].document_id}-chunk-0",
                    source_id=source.source_id,
                    snapshot_id=snapshot.snapshot_id,
                    document_id=documents[0].document_id,
                    chunk_index=0,
                    text="shared query text from active content",
                    metadata={},
                ),
                Chunk(
                    chunk_id=f"{documents[1].document_id}-chunk-0",
                    source_id=source.source_id,
                    snapshot_id=snapshot.snapshot_id,
                    document_id=documents[1].document_id,
                    chunk_index=0,
                    text="shared query text from reference content",
                    metadata={"section_path": ["Reference"]},
                ),
            ],
        )
        store.activate_snapshot(source.source_id, snapshot.snapshot_id)
        return store

    def _query_local_json(self, store: SQLiteStore, text: str) -> _TraceEnvelope:
        module = import_module("locontext.app.query")
        query_local_json = cast(
            _QueryLocalJson | None, getattr(module, "query_local_json", None)
        )
        if query_local_json is None:
            raise AssertionError("expected locontext.app.query.query_local_json")
        return query_local_json(store, text, limit=5)

    def test_query_json_hit_contains_trace_fields(self) -> None:
        store = self._seed_query_state()
        envelope = self._query_local_json(store, "shared query text")
        assert [hit.document_locator for hit in envelope.hits] == [
            "https://docs.example.com/docs/guide",
            "https://docs.example.com/docs/reference",
        ]
        assert envelope.hits[0].rank == 1
        assert envelope.hits[0].source_locator == "https://docs.example.com/docs"
        assert envelope.hits[0].matched_terms == ["shared", "query", "text"]
        assert envelope.hits[0].match_query == '"shared" AND "query" AND "text"'
        assert envelope.hits[1].section_path == ["Reference"]
        assert envelope.hits[1].metadata == {"section_path": ["Reference"]}

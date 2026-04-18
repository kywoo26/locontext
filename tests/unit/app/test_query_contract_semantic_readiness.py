from importlib import import_module
from typing import Protocol, cast

import pytest

from locontext.domain.models import (
    Chunk,
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


class _LocalQueryEngineDescriptor(Protocol):
    engine_kind: str
    engine_name: str
    semantic_ready: bool
    is_baseline: bool


class _DescribeLocalQueryEngine(Protocol):
    def __call__(self, store: SQLiteStore) -> _LocalQueryEngineDescriptor: ...


class _QueryEnvelope(Protocol):
    def as_dict(self) -> dict[str, object]: ...


class _QueryLocalJson(Protocol):
    def __call__(
        self,
        store: SQLiteStore,
        text: str,
        *,
        limit: int,
        source_id: str | None = None,
    ) -> _QueryEnvelope: ...


def _query_module() -> object:
    try:
        return import_module("locontext.app.query")
    except ModuleNotFoundError as exc:
        raise AssertionError(f"expected locontext.app.query module: {exc}") from exc


def _describe_local_query_engine(store: SQLiteStore) -> _LocalQueryEngineDescriptor:
    module = _query_module()
    describe_local_query_engine = cast(
        _DescribeLocalQueryEngine | None,
        getattr(module, "describe_local_query_engine", None),
    )
    if describe_local_query_engine is None:
        raise AssertionError("expected locontext.app.query.describe_local_query_engine")
    return describe_local_query_engine(store)


def _query_local_json(
    store: SQLiteStore, text: str, *, limit: int, source_id: str | None = None
) -> dict[str, object]:
    module = _query_module()
    query_local_json = cast(
        _QueryLocalJson | None, getattr(module, "query_local_json", None)
    )
    if query_local_json is None:
        raise AssertionError("expected locontext.app.query.query_local_json")
    return query_local_json(store, text, limit=limit, source_id=source_id).as_dict()


@pytest.fixture()
def seeded_store(store: SQLiteStore) -> SQLiteStore:
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
            )
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
            )
        ],
    )
    store.activate_snapshot(source.source_id, snapshot.snapshot_id)

    other_source = Source(
        source_id="source-2",
        source_kind=SourceKind.WEB,
        requested_locator="https://docs.example.com/other",
        resolved_locator="https://docs.example.com/other",
        canonical_locator="https://docs.example.com/other",
        docset_root="https://docs.example.com/other",
    )
    store.upsert_source(other_source)
    other_snapshot = Snapshot(
        snapshot_id="snapshot-other",
        source_id=other_source.source_id,
        status=SnapshotStatus.INDEXED,
        content_hash="hash-other",
        is_active=True,
    )
    store.insert_snapshot(other_snapshot)
    other_documents = store.replace_snapshot_documents(
        other_snapshot.snapshot_id,
        other_source.source_id,
        [
            DiscoveredDocument(
                requested_locator="https://docs.example.com/other/page",
                resolved_locator="https://docs.example.com/other/page",
                canonical_locator="https://docs.example.com/other/page",
                title="Other Guide",
                content_hash="doc-hash-other",
            )
        ],
    )
    store.replace_snapshot_chunks(
        other_snapshot.snapshot_id,
        [
            Chunk(
                chunk_id=f"{other_documents[0].document_id}-chunk-0",
                source_id=other_source.source_id,
                snapshot_id=other_snapshot.snapshot_id,
                document_id=other_documents[0].document_id,
                chunk_index=0,
                text="shared query text from other source content",
                metadata={"section_path": ["Other"]},
            )
        ],
    )
    store.activate_snapshot(other_source.source_id, other_snapshot.snapshot_id)
    return store


def test_local_query_engine_descriptor_reports_lexical_baseline(
    store: SQLiteStore,
) -> None:
    descriptor = _describe_local_query_engine(store)
    assert descriptor.engine_kind == "lexical"
    assert descriptor.engine_name == "sqlite_lexical"
    assert not descriptor.semantic_ready
    assert descriptor.is_baseline


def test_query_json_payload_omits_readiness_metadata(seeded_store: SQLiteStore) -> None:
    payload = _query_local_json(seeded_store, "shared query text", limit=2)
    assert list(payload.keys()) == ["query", "hit_count", "hits"]
    assert list(cast(dict[str, object], payload["query"]).keys()) == [
        "text",
        "limit",
        "source_id",
    ]
    assert "semantic_ready" not in payload
    assert "engine_kind" not in payload
    assert "engine_name" not in payload
    assert "is_baseline" not in payload


def test_no_hit_json_payload_stays_unchanged_when_semantic_is_not_ready(
    seeded_store: SQLiteStore,
) -> None:
    payload = _query_local_json(seeded_store, "definitely-no-hit", limit=5)
    assert list(payload.keys()) == ["query", "hit_count", "hits"]
    assert payload["query"] == {
        "text": "definitely-no-hit",
        "limit": 5,
        "source_id": None,
    }
    assert payload["hit_count"] == 0
    assert payload["hits"] == []
    assert "semantic_ready" not in payload


def test_source_filtered_json_payload_stays_unchanged_when_semantic_is_not_ready(
    seeded_store: SQLiteStore,
) -> None:
    payload = _query_local_json(
        seeded_store,
        "shared query text",
        limit=5,
        source_id="source-2",
    )
    assert list(payload.keys()) == ["query", "hit_count", "hits"]
    assert payload["query"] == {
        "text": "shared query text",
        "limit": 5,
        "source_id": "source-2",
    }
    assert payload["hit_count"] == 1
    assert len(cast(list[object], payload["hits"])) == 1
    assert "semantic_ready" not in payload

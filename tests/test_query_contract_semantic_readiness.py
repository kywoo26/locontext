from __future__ import annotations

import sqlite3
import unittest
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


class QuerySemanticReadinessContractTest(unittest.TestCase):
    connection: sqlite3.Connection  # pyright: ignore[reportUninitializedInstanceVariable]
    store: SQLiteStore  # pyright: ignore[reportUninitializedInstanceVariable]

    def setUp(self) -> None:  # pyright: ignore[reportImplicitOverride]
        super().setUp()
        self.connection = sqlite3.connect(":memory:")
        self.store = SQLiteStore(self.connection)
        self.store.ensure_schema()
        self.addCleanup(self.connection.close)

    def _query_module(self):
        try:
            return import_module("locontext.app.query")
        except ModuleNotFoundError as exc:
            self.fail(f"expected locontext.app.query module: {exc}")

    def _describe_local_query_engine(self) -> _LocalQueryEngineDescriptor:
        module = self._query_module()
        describe_local_query_engine = cast(
            _DescribeLocalQueryEngine | None,
            getattr(module, "describe_local_query_engine", None),
        )
        if describe_local_query_engine is None:
            self.fail("expected locontext.app.query.describe_local_query_engine")
        return describe_local_query_engine(self.store)

    def _query_local_json(
        self,
        text: str,
        *,
        limit: int,
        source_id: str | None = None,
    ) -> dict[str, object]:
        module = self._query_module()
        query_local_json = cast(
            _QueryLocalJson | None,
            getattr(module, "query_local_json", None),
        )
        if query_local_json is None:
            self.fail("expected locontext.app.query.query_local_json")
        return query_local_json(
            self.store, text, limit=limit, source_id=source_id
        ).as_dict()

    def _seed_query_state(self) -> None:
        source = Source(
            source_id="source-1",
            source_kind=SourceKind.WEB,
            requested_locator="https://docs.example.com/docs",
            resolved_locator="https://docs.example.com/docs",
            canonical_locator="https://docs.example.com/docs",
            docset_root="https://docs.example.com/docs",
        )
        self.store.upsert_source(source)

        snapshot = Snapshot(
            snapshot_id="snapshot-active",
            source_id=source.source_id,
            status=SnapshotStatus.INDEXED,
            content_hash="hash-active",
            is_active=True,
        )
        self.store.insert_snapshot(snapshot)
        documents = self.store.replace_snapshot_documents(
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
        self.store.replace_snapshot_chunks(
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
        self.store.activate_snapshot(source.source_id, snapshot.snapshot_id)

        other_source = Source(
            source_id="source-2",
            source_kind=SourceKind.WEB,
            requested_locator="https://docs.example.com/other",
            resolved_locator="https://docs.example.com/other",
            canonical_locator="https://docs.example.com/other",
            docset_root="https://docs.example.com/other",
        )
        self.store.upsert_source(other_source)

        other_snapshot = Snapshot(
            snapshot_id="snapshot-other",
            source_id=other_source.source_id,
            status=SnapshotStatus.INDEXED,
            content_hash="hash-other",
            is_active=True,
        )
        self.store.insert_snapshot(other_snapshot)
        other_documents = self.store.replace_snapshot_documents(
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
        self.store.replace_snapshot_chunks(
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
        self.store.activate_snapshot(other_source.source_id, other_snapshot.snapshot_id)

    def test_local_query_engine_descriptor_reports_lexical_baseline(self) -> None:
        descriptor = self._describe_local_query_engine()

        self.assertEqual(descriptor.engine_kind, "lexical")
        self.assertEqual(descriptor.engine_name, "sqlite_lexical")
        self.assertFalse(descriptor.semantic_ready)
        self.assertTrue(descriptor.is_baseline)

    def test_query_json_payload_omits_readiness_metadata(self) -> None:
        self._seed_query_state()

        payload = self._query_local_json("shared query text", limit=2)

        self.assertEqual(list(payload.keys()), ["query", "hit_count", "hits"])
        self.assertEqual(
            list(cast(dict[str, object], payload["query"]).keys()),
            ["text", "limit", "source_id"],
        )
        self.assertNotIn("semantic_ready", payload)
        self.assertNotIn("engine_kind", payload)
        self.assertNotIn("engine_name", payload)
        self.assertNotIn("is_baseline", payload)

    def test_no_hit_json_payload_stays_unchanged_when_semantic_is_not_ready(
        self,
    ) -> None:
        self._seed_query_state()

        payload = self._query_local_json("definitely-no-hit", limit=5)

        self.assertEqual(list(payload.keys()), ["query", "hit_count", "hits"])
        self.assertEqual(
            payload["query"],
            {"text": "definitely-no-hit", "limit": 5, "source_id": None},
        )
        self.assertEqual(payload["hit_count"], 0)
        self.assertEqual(payload["hits"], [])
        self.assertNotIn("semantic_ready", payload)

    def test_source_filtered_json_payload_stays_unchanged_when_semantic_is_not_ready(
        self,
    ) -> None:
        self._seed_query_state()

        payload = self._query_local_json(
            "shared query text",
            limit=5,
            source_id="source-2",
        )

        self.assertEqual(list(payload.keys()), ["query", "hit_count", "hits"])
        self.assertEqual(
            payload["query"],
            {"text": "shared query text", "limit": 5, "source_id": "source-2"},
        )
        self.assertEqual(payload["hit_count"], 1)
        self.assertEqual(len(cast(list[object], payload["hits"])), 1)
        self.assertNotIn("semantic_ready", payload)


if __name__ == "__main__":
    _ = unittest.main()

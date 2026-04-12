from __future__ import annotations

import sqlite3
import unittest

from locontext.app.sources import list_sources, register_source, remove_source
from locontext.domain.models import (
    Chunk,
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


class SourceRegistryTest(unittest.TestCase):
    connection: sqlite3.Connection  # pyright: ignore[reportUninitializedInstanceVariable]
    store: SQLiteStore  # pyright: ignore[reportUninitializedInstanceVariable]

    def setUp(self) -> None:  # pyright: ignore[reportImplicitOverride]
        self.connection = sqlite3.connect(":memory:")
        self.store = SQLiteStore(self.connection)
        self.store.ensure_schema()

    def test_register_source_creates_web_source(self) -> None:
        result = register_source(
            self.store,
            "https://docs.example.com/docs/getting-started?utm_source=test#intro",
        )

        self.assertTrue(result.created)
        self.assertEqual(
            result.source.canonical_locator,
            "https://docs.example.com/docs/getting-started",
        )
        self.assertEqual(result.source.docset_root, "https://docs.example.com")

    def test_register_source_dedupes_equivalent_urls(self) -> None:
        first = register_source(
            self.store,
            "https://docs.example.com/docs/getting-started?utm_source=test#intro",
        )
        second = register_source(
            self.store,
            "https://docs.example.com/docs/getting-started",
        )

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.source.source_id, second.source.source_id)

    def test_list_sources_is_deterministic(self) -> None:
        _ = register_source(self.store, "https://docs.example.com/docs/beta")
        _ = register_source(self.store, "https://docs.example.com/docs/alpha")

        sources = list_sources(self.store)

        self.assertEqual(
            [source.canonical_locator for source in sources],
            [
                "https://docs.example.com/docs/alpha",
                "https://docs.example.com/docs/beta",
            ],
        )

    def test_remove_source_deletes_related_local_state(self) -> None:
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
            snapshot_id="snapshot-1",
            source_id=source.source_id,
            status=SnapshotStatus.INDEXED,
            is_active=True,
        )
        self.store.insert_snapshot(snapshot)
        stored_documents = self.store.replace_snapshot_documents(
            snapshot.snapshot_id,
            source.source_id,
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/page",
                    resolved_locator="https://docs.example.com/docs/page",
                    canonical_locator="https://docs.example.com/docs/page",
                    title="Page",
                    content_hash="hash-1",
                )
            ],
        )
        self.store.replace_snapshot_chunks(
            snapshot.snapshot_id,
            [
                Chunk(
                    chunk_id="chunk-1",
                    source_id=source.source_id,
                    snapshot_id=snapshot.snapshot_id,
                    document_id=stored_documents[0].document_id,
                    chunk_index=0,
                    text="hello world",
                )
            ],
        )
        self.store.activate_snapshot(source.source_id, snapshot.snapshot_id)

        result = remove_source(self.store, source.source_id)

        self.assertTrue(result.removed)
        self.assertIsNone(self.store.get_source(source.source_id))
        self.assertIsNone(self.store.get_active_snapshot(source.source_id))
        self.assertEqual(self.store.list_documents(snapshot.snapshot_id), [])
        self.assertEqual(self.store.search_chunks("hello", limit=10), [])

    def test_remove_source_is_idempotent_for_missing_source(self) -> None:
        first = remove_source(self.store, "missing-source")
        second = remove_source(self.store, "missing-source")

        self.assertFalse(first.removed)
        self.assertFalse(second.removed)
        self.assertEqual(first.source_id, "missing-source")
        self.assertEqual(second.source_id, "missing-source")


if __name__ == "__main__":
    _ = unittest.main()

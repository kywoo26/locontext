from __future__ import annotations

import sqlite3
import unittest
from typing import override

from locontext.app.sources import get_source_status, list_source_status
from locontext.domain.models import (
    Chunk,
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


class SourceStatusTest(unittest.TestCase):
    connection: sqlite3.Connection  # pyright: ignore[reportUninitializedInstanceVariable]
    store: SQLiteStore  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.store = SQLiteStore(self.connection)
        self.store.ensure_schema()

    def _add_source(self, source_id: str, locator: str) -> Source:
        source = Source(
            source_id=source_id,
            source_kind=SourceKind.WEB,
            requested_locator=locator,
            resolved_locator=locator,
            canonical_locator=locator,
            docset_root=locator,
        )
        self.store.upsert_source(source)
        return source

    def test_list_source_status_is_stable_for_unrefreshed_sources(self) -> None:
        _ = self._add_source("source-b", "https://docs.example.com/docs/b")
        _ = self._add_source("source-a", "https://docs.example.com/docs/a")

        statuses = list_source_status(self.store)

        self.assertEqual(
            [status.source_id for status in statuses], ["source-a", "source-b"]
        )
        self.assertEqual([status.document_count for status in statuses], [0, 0])
        self.assertEqual([status.chunk_count for status in statuses], [0, 0])
        self.assertEqual(
            [status.active_snapshot_id for status in statuses], [None, None]
        )
        self.assertEqual([status.snapshot_status for status in statuses], [None, None])
        self.assertEqual([status.fetched_at for status in statuses], [None, None])
        self.assertEqual(
            [status.freshness_state for status in statuses],
            ["never-refreshed", "never-refreshed"],
        )

    def test_list_source_status_keeps_never_refreshed_and_unhealthy_empty_distinct(
        self,
    ) -> None:
        never_refreshed = self._add_source(
            "source-b", "https://docs.example.com/docs/b"
        )
        active_zero_document = self._add_source(
            "source-a", "https://docs.example.com/docs/a"
        )
        snapshot = Snapshot(
            snapshot_id="snapshot-0",
            source_id=active_zero_document.source_id,
            status=SnapshotStatus.INDEXED,
            fetched_at="2026-04-12T00:00:00+00:00",
            is_active=True,
        )
        self.store.insert_snapshot(snapshot)
        _ = self.store.replace_snapshot_documents(
            snapshot.snapshot_id,
            active_zero_document.source_id,
            [],
        )
        self.store.activate_snapshot(
            active_zero_document.source_id, snapshot.snapshot_id
        )

        statuses = list_source_status(self.store)

        self.assertEqual(
            [status.source_id for status in statuses],
            [active_zero_document.source_id, never_refreshed.source_id],
        )
        self.assertEqual([status.document_count for status in statuses], [0, 0])
        self.assertEqual([status.chunk_count for status in statuses], [0, 0])
        self.assertEqual(
            [status.active_snapshot_id for status in statuses],
            [snapshot.snapshot_id, None],
        )
        self.assertEqual(
            [status.freshness_state for status in statuses],
            ["unhealthy-empty", "never-refreshed"],
        )
        self.assertEqual(
            [status.freshness_reason for status in statuses],
            ["zero documents in active snapshot", "source has never been refreshed"],
        )

    def test_get_source_status_reports_active_snapshot_counts(self) -> None:
        source = self._add_source("source-1", "https://docs.example.com/docs")
        snapshot = Snapshot(
            snapshot_id="snapshot-1",
            source_id=source.source_id,
            status=SnapshotStatus.INDEXED,
            fetched_at="2026-04-12T00:00:00+00:00",
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
                    content_hash="doc-hash-1",
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
                    text="hello world",
                )
            ],
        )
        status = get_source_status(self.store, source.source_id)

        self.assertIsNotNone(status)
        if status is None:
            self.fail("expected source status")
        self.assertEqual(status.source_id, source.source_id)
        self.assertEqual(status.active_snapshot_id, snapshot.snapshot_id)
        self.assertEqual(status.snapshot_status, SnapshotStatus.INDEXED)
        self.assertEqual(status.document_count, 1)
        self.assertEqual(status.chunk_count, 1)
        self.assertEqual(status.fetched_at, "2026-04-12T00:00:00+00:00")
        self.assertEqual(status.freshness_state, "current")

    def test_get_source_status_reports_unhealthy_empty_for_active_zero_documents(
        self,
    ) -> None:
        source = self._add_source("source-2", "https://docs.example.com/docs")
        snapshot = Snapshot(
            snapshot_id="snapshot-2",
            source_id=source.source_id,
            status=SnapshotStatus.INDEXED,
            fetched_at="2026-04-12T00:00:00+00:00",
            is_active=True,
        )
        self.store.insert_snapshot(snapshot)
        _ = self.store.replace_snapshot_documents(
            snapshot.snapshot_id,
            source.source_id,
            [],
        )
        status = get_source_status(self.store, source.source_id)

        self.assertIsNotNone(status)
        if status is None:
            self.fail("expected source status")
        self.assertEqual(status.document_count, 0)
        self.assertEqual(status.chunk_count, 0)
        self.assertEqual(status.freshness_state, "unhealthy-empty")
        self.assertEqual(status.freshness_reason, "zero documents in active snapshot")

    def test_get_source_status_keeps_stale_advisory_for_non_empty_stale_snapshot(
        self,
    ) -> None:
        source = self._add_source("source-3", "https://docs.example.com/docs")
        snapshot = Snapshot(
            snapshot_id="snapshot-3",
            source_id=source.source_id,
            status=SnapshotStatus.STALE,
            fetched_at="2026-04-12T00:00:00+00:00",
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
                    content_hash="doc-hash-1",
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
                    text="hello world",
                )
            ],
        )
        status = get_source_status(self.store, source.source_id)

        self.assertIsNotNone(status)
        if status is None:
            self.fail("expected source status")
        self.assertEqual(status.document_count, 1)
        self.assertEqual(status.chunk_count, 1)
        self.assertEqual(status.freshness_state, "stale-advisory")
        self.assertEqual(
            status.freshness_reason,
            "active snapshot is stale until manually refreshed",
        )

    def test_get_source_status_returns_none_for_missing_source(self) -> None:
        self.assertIsNone(get_source_status(self.store, "missing-source"))


if __name__ == "__main__":
    _ = unittest.main()

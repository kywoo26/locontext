from __future__ import annotations

import sqlite3
import unittest
from typing import override

from locontext.app.refresh import get_freshness_state
from locontext.domain.models import (
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


class RefreshFreshnessContractTest(unittest.TestCase):
    connection: sqlite3.Connection  # pyright: ignore[reportUninitializedInstanceVariable]
    store: SQLiteStore  # pyright: ignore[reportUninitializedInstanceVariable]
    source: Source  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.store = SQLiteStore(self.connection)
        self.store.ensure_schema()
        self.source = Source(
            source_id="source-1",
            source_kind=SourceKind.WEB,
            requested_locator="https://docs.example.com/docs",
            resolved_locator="https://docs.example.com/docs",
            canonical_locator="https://docs.example.com/docs",
            docset_root="https://docs.example.com/docs",
        )
        self.store.upsert_source(self.source)

    def _activate_snapshot(
        self,
        *,
        snapshot_id: str,
        status: SnapshotStatus,
        documents: list[DiscoveredDocument] | None = None,
    ) -> Snapshot:
        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            source_id=self.source.source_id,
            status=status,
            fetched_at="2026-04-12T00:00:00+00:00",
            is_active=True,
        )
        self.store.insert_snapshot(snapshot)
        if documents is not None:
            _ = self.store.replace_snapshot_documents(
                snapshot.snapshot_id,
                self.source.source_id,
                documents,
            )
        self.store.activate_snapshot(self.source.source_id, snapshot.snapshot_id)
        if status is SnapshotStatus.STALE:
            self.store.mark_snapshot_stale(snapshot.snapshot_id)
        return snapshot

    def test_never_refreshed_source_reports_never_refreshed(self) -> None:
        state = get_freshness_state(self.store, self.source.source_id)

        self.assertEqual(state.code, "never-refreshed")
        self.assertEqual(state.reason, "source has never been refreshed")

    def test_active_snapshot_with_zero_documents_is_unhealthy_empty(self) -> None:
        _ = self._activate_snapshot(
            snapshot_id="snapshot-1",
            status=SnapshotStatus.INDEXED,
            documents=[],
        )

        state = get_freshness_state(self.store, self.source.source_id)

        self.assertEqual(state.code, "unhealthy-empty")
        self.assertEqual(state.reason, "zero documents in active snapshot")

    def test_active_stale_snapshot_with_zero_documents_is_unhealthy_empty(self) -> None:
        _ = self._activate_snapshot(
            snapshot_id="snapshot-1",
            status=SnapshotStatus.STALE,
            documents=[],
        )

        state = get_freshness_state(self.store, self.source.source_id)

        self.assertEqual(state.code, "unhealthy-empty")
        self.assertEqual(state.reason, "zero documents in active snapshot")

    def test_active_snapshot_with_documents_is_current(self) -> None:
        _ = self._activate_snapshot(
            snapshot_id="snapshot-1",
            status=SnapshotStatus.INDEXED,
            documents=[
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/guide",
                    resolved_locator="https://docs.example.com/docs/guide",
                    canonical_locator="https://docs.example.com/docs/guide",
                    title="Guide",
                    content_hash="doc-hash-1",
                )
            ],
        )

        state = get_freshness_state(self.store, self.source.source_id)

        self.assertEqual(state.code, "current")
        self.assertEqual(state.reason, "active snapshot is current")

    def test_active_stale_snapshot_with_documents_is_advisory_only(self) -> None:
        _ = self._activate_snapshot(
            snapshot_id="snapshot-1",
            status=SnapshotStatus.STALE,
            documents=[
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/guide",
                    resolved_locator="https://docs.example.com/docs/guide",
                    canonical_locator="https://docs.example.com/docs/guide",
                    title="Guide",
                    content_hash="doc-hash-1",
                )
            ],
        )

        state = get_freshness_state(self.store, self.source.source_id)

        self.assertEqual(state.code, "stale-advisory")
        self.assertEqual(
            state.reason, "active snapshot is stale until manually refreshed"
        )


if __name__ == "__main__":
    _ = unittest.main()

from __future__ import annotations

import sqlite3
import unittest
from typing import override

from locontext.app.refresh import get_freshness_state
from locontext.domain.models import Snapshot, SnapshotStatus, Source, SourceKind
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

    def test_never_refreshed_source_reports_never_refreshed(self) -> None:
        state = get_freshness_state(self.store, self.source.source_id)

        self.assertEqual(state.code, "never-refreshed")
        self.assertEqual(state.reason, "source has never been refreshed")

    def test_active_snapshot_without_stale_mark_is_current(self) -> None:
        snapshot = Snapshot(
            snapshot_id="snapshot-1",
            source_id=self.source.source_id,
            status=SnapshotStatus.INDEXED,
            fetched_at="2026-04-12T00:00:00+00:00",
            is_active=True,
        )
        self.store.insert_snapshot(snapshot)
        self.store.activate_snapshot(self.source.source_id, snapshot.snapshot_id)

        state = get_freshness_state(self.store, self.source.source_id)

        self.assertEqual(state.code, "current")
        self.assertEqual(state.reason, "active snapshot is current")

    def test_active_snapshot_marked_stale_is_advisory_only(self) -> None:
        snapshot = Snapshot(
            snapshot_id="snapshot-1",
            source_id=self.source.source_id,
            status=SnapshotStatus.STALE,
            fetched_at="2026-04-12T00:00:00+00:00",
            is_active=True,
        )
        self.store.insert_snapshot(snapshot)
        self.store.activate_snapshot(self.source.source_id, snapshot.snapshot_id)
        self.store.mark_snapshot_stale(snapshot.snapshot_id)

        state = get_freshness_state(self.store, self.source.source_id)

        self.assertEqual(state.code, "stale-advisory")
        self.assertEqual(
            state.reason, "active snapshot is stale until manually refreshed"
        )


if __name__ == "__main__":
    _ = unittest.main()

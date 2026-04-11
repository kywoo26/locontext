from __future__ import annotations

import sqlite3
import unittest

from locontext.app.refresh import RefreshOrchestrator
from locontext.domain.models import DiscoveredDocument, Source, SourceKind
from locontext.store.sqlite import SQLiteStore


class _FakeDiscoveryProvider:
    def __init__(self, payloads: list[list[DiscoveredDocument]]) -> None:
        self._payloads = list(payloads)
        self.calls = 0

    def discover(self, source: Source) -> list[DiscoveredDocument]:
        self.calls += 1
        if self._payloads:
            return self._payloads.pop(0)
        return []


class _FakeIndexingEngine:
    def __init__(self) -> None:
        self.reindex_calls: list[tuple[str, str, int]] = []
        self.remove_calls: list[str] = []

    def reindex_snapshot(self, source: Source, snapshot, documents) -> None:  # noqa: ANN001
        self.reindex_calls.append(
            (source.source_id, snapshot.snapshot_id, len(documents))
        )

    def remove_source(self, source_id: str) -> None:
        self.remove_calls.append(source_id)


class RefreshOrchestratorTest(unittest.TestCase):
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

    def test_unchanged_refresh_reuses_active_snapshot(self) -> None:
        documents = [
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/intro",
                    resolved_locator="https://docs.example.com/docs/intro",
                    canonical_locator="https://docs.example.com/docs/intro",
                    content_hash="hash-1",
                )
            ],
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/intro",
                    resolved_locator="https://docs.example.com/docs/intro",
                    canonical_locator="https://docs.example.com/docs/intro",
                    content_hash="hash-1",
                )
            ],
        ]
        discovery = _FakeDiscoveryProvider(documents)
        engine = _FakeIndexingEngine()
        orchestrator = RefreshOrchestrator(self.store, discovery, engine)

        first = orchestrator.refresh_source("source-1")
        second = orchestrator.refresh_source("source-1")

        self.assertTrue(first.changed)
        self.assertFalse(second.changed)
        self.assertEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(len(engine.reindex_calls), 1)

    def test_changed_refresh_creates_new_active_snapshot(self) -> None:
        discovery = _FakeDiscoveryProvider(
            [
                [
                    DiscoveredDocument(
                        requested_locator="https://docs.example.com/docs/intro",
                        resolved_locator="https://docs.example.com/docs/intro",
                        canonical_locator="https://docs.example.com/docs/intro",
                        content_hash="hash-1",
                    )
                ],
                [
                    DiscoveredDocument(
                        requested_locator="https://docs.example.com/docs/intro",
                        resolved_locator="https://docs.example.com/docs/intro",
                        canonical_locator="https://docs.example.com/docs/intro",
                        content_hash="hash-2",
                    )
                ],
            ]
        )
        engine = _FakeIndexingEngine()
        orchestrator = RefreshOrchestrator(self.store, discovery, engine)

        first = orchestrator.refresh_source("source-1")
        second = orchestrator.refresh_source("source-1")
        active = self.store.get_active_snapshot("source-1")

        self.assertNotEqual(first.snapshot_id, second.snapshot_id)
        if active is None:
            self.fail("expected an active snapshot")
        self.assertEqual(active.snapshot_id, second.snapshot_id)
        self.assertEqual(len(engine.reindex_calls), 2)

    def test_reindex_source_uses_active_snapshot_without_discovery(self) -> None:
        discovery = _FakeDiscoveryProvider(
            [
                [
                    DiscoveredDocument(
                        requested_locator="https://docs.example.com/docs/intro",
                        resolved_locator="https://docs.example.com/docs/intro",
                        canonical_locator="https://docs.example.com/docs/intro",
                        content_hash="hash-1",
                    )
                ]
            ]
        )
        engine = _FakeIndexingEngine()
        orchestrator = RefreshOrchestrator(self.store, discovery, engine)
        orchestrator.refresh_source("source-1")

        before = discovery.calls
        result = orchestrator.reindex_source("source-1")

        self.assertEqual(discovery.calls, before)
        self.assertEqual(result.document_count, 1)
        self.assertEqual(len(engine.reindex_calls), 2)

    def test_remove_source_deletes_local_state_and_invokes_engine(self) -> None:
        discovery = _FakeDiscoveryProvider(
            [
                [
                    DiscoveredDocument(
                        requested_locator="https://docs.example.com/docs/intro",
                        resolved_locator="https://docs.example.com/docs/intro",
                        canonical_locator="https://docs.example.com/docs/intro",
                        content_hash="hash-1",
                    )
                ]
            ]
        )
        engine = _FakeIndexingEngine()
        orchestrator = RefreshOrchestrator(self.store, discovery, engine)
        orchestrator.refresh_source("source-1")

        orchestrator.remove_source("source-1")

        self.assertEqual(engine.remove_calls, ["source-1"])
        self.assertIsNone(self.store.get_source("source-1"))


if __name__ == "__main__":
    unittest.main()

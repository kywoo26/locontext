from __future__ import annotations

import sqlite3
import unittest
from collections.abc import Sequence
from importlib import import_module

import httpx

from locontext.app.refresh import RefreshOrchestrator
from locontext.domain.models import Document, Snapshot, Source, SourceKind
from locontext.store.sqlite import SQLiteStore


class _RecordingIndexingEngine:
    def __init__(self) -> None:
        super().__init__()
        self.reindex_calls: list[tuple[str, str, int]] = []
        self.remove_calls: list[str] = []

    def reindex_snapshot(
        self,
        source: Source,
        snapshot: Snapshot,
        documents: Sequence[Document],
    ) -> None:
        self.reindex_calls.append(
            (source.source_id, snapshot.snapshot_id, len(documents))
        )

    def remove_source(self, source_id: str) -> None:
        self.remove_calls.append(source_id)


class RefreshOrchestratorTest(unittest.TestCase):
    connection: sqlite3.Connection  # pyright: ignore[reportUninitializedInstanceVariable]
    store: SQLiteStore  # pyright: ignore[reportUninitializedInstanceVariable]
    source: Source  # pyright: ignore[reportUninitializedInstanceVariable]

    def setUp(self) -> None:  # pyright: ignore[reportImplicitOverride]
        super().setUp()
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

    def _make_orchestrator(
        self, responses: list[tuple[str, str]]
    ) -> tuple[RefreshOrchestrator, _RecordingIndexingEngine]:
        remaining = list(responses)

        def handler(request: httpx.Request) -> httpx.Response:
            if not remaining:
                self.fail(f"unexpected request: {request.url}")
            body, content_type = remaining.pop(0)
            return httpx.Response(
                200,
                headers={"content-type": content_type},
                text=body,
                request=request,
            )

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport, follow_redirects=True)
        self.addCleanup(client.close)
        provider_module = import_module("locontext.sources.web.provider")
        provider = provider_module.WebDiscoveryProvider(client=client)
        engine = _RecordingIndexingEngine()
        return RefreshOrchestrator(self.store, provider, engine), engine

    def test_unchanged_refresh_reuses_active_snapshot(self) -> None:
        orchestrator, engine = self._make_orchestrator(
            [
                (
                    "<html><head><title>Intro</title></head><body>Hello world</body></html>",
                    "text/html; charset=utf-8",
                ),
                (
                    "<html><head><title>Intro</title></head><body>Hello world</body></html>",
                    "text/html; charset=utf-8",
                ),
            ]
        )

        first = orchestrator.refresh_source("source-1")
        second = orchestrator.refresh_source("source-1")

        self.assertTrue(first.changed)
        self.assertFalse(second.changed)
        self.assertEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(len(engine.reindex_calls), 1)
        if first.snapshot_id is None:
            self.fail("expected a snapshot id")
        stored_documents = self.store.list_documents(first.snapshot_id)
        self.assertEqual(len(stored_documents), 1)
        self.assertEqual(stored_documents[0].title, "Intro")
        self.assertIsNotNone(stored_documents[0].content_hash)

    def test_changed_refresh_creates_new_active_snapshot(self) -> None:
        orchestrator, engine = self._make_orchestrator(
            [
                (
                    "<html><head><title>Intro</title></head><body>Hello world</body></html>",
                    "text/html; charset=utf-8",
                ),
                (
                    "<html><head><title>Intro</title></head><body>Hello again</body></html>",
                    "text/html; charset=utf-8",
                ),
            ]
        )

        first = orchestrator.refresh_source("source-1")
        second = orchestrator.refresh_source("source-1")
        active = self.store.get_active_snapshot("source-1")

        self.assertNotEqual(first.snapshot_id, second.snapshot_id)
        if active is None:
            self.fail("expected an active snapshot")
        self.assertEqual(active.snapshot_id, second.snapshot_id)
        self.assertEqual(len(engine.reindex_calls), 2)

    def test_reindex_source_uses_active_snapshot_without_discovery(self) -> None:
        orchestrator, engine = self._make_orchestrator(
            [
                (
                    "<html><head><title>Intro</title></head><body>Hello world</body></html>",
                    "text/html; charset=utf-8",
                )
            ]
        )
        _ = orchestrator.refresh_source("source-1")

        result = orchestrator.reindex_source("source-1")

        self.assertEqual(result.document_count, 1)
        self.assertEqual(len(engine.reindex_calls), 2)

    def test_remove_source_deletes_local_state_and_invokes_engine(self) -> None:
        orchestrator, engine = self._make_orchestrator(
            [
                (
                    "<html><head><title>Intro</title></head><body>Hello world</body></html>",
                    "text/html; charset=utf-8",
                )
            ]
        )
        _ = orchestrator.refresh_source("source-1")

        orchestrator.remove_source("source-1")

        self.assertEqual(engine.remove_calls, ["source-1"])
        self.assertIsNone(self.store.get_source("source-1"))


if __name__ == "__main__":
    _ = unittest.main()

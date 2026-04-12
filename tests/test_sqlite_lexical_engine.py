from __future__ import annotations

import sqlite3
import unittest
from collections.abc import Sequence
from importlib import import_module
from typing import Protocol, cast

from locontext.domain.models import (
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


class _QueryHitLike(Protocol):
    snapshot_id: str
    chunk_id: str
    chunk_index: int
    text: str


class _SQLiteLexicalEngineLike(Protocol):
    def reindex_snapshot(
        self,
        source: Source,
        snapshot: Snapshot,
        documents: Sequence[object],
    ) -> None: ...

    def query(self, text: str, *, limit: int) -> list[_QueryHitLike]: ...


class SQLiteLexicalEngineContractTest(unittest.TestCase):
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

    def _make_engine(self) -> _SQLiteLexicalEngineLike:
        try:
            module = import_module("locontext.engine.sqlite_lexical")
        except ModuleNotFoundError as exc:
            self.fail(f"expected locontext.engine.sqlite_lexical module: {exc}")

        engine_class = getattr(module, "SQLiteLexicalEngine", None)
        if engine_class is None:
            self.fail("expected locontext.engine.sqlite_lexical.SQLiteLexicalEngine")
        return cast(_SQLiteLexicalEngineLike, engine_class(self.connection))

    def _insert_snapshot_with_chunks(
        self,
        snapshot_id: str,
        *,
        active: bool,
        status: SnapshotStatus,
        document_locator: str,
        chunks: list[str],
    ) -> None:
        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            source_id=self.source.source_id,
            status=status,
            content_hash=f"hash-{snapshot_id}",
            is_active=active,
        )
        self.store.insert_snapshot(snapshot)
        _ = self.store.replace_snapshot_documents(
            snapshot_id,
            self.source.source_id,
            [
                DiscoveredDocument(
                    requested_locator=document_locator,
                    resolved_locator=document_locator,
                    canonical_locator=document_locator,
                    title=document_locator.rsplit("/", maxsplit=1)[-1],
                    content_hash=f"doc-hash-{snapshot_id}",
                )
            ],
        )
        document_id = f"{snapshot_id}-doc-0"
        for chunk_index, text in enumerate(chunks):
            chunk_id = f"{document_id}-chunk-{chunk_index}"
            _ = self.connection.execute(
                """
                INSERT INTO chunks (
                    chunk_id,
                    source_id,
                    snapshot_id,
                    document_id,
                    chunk_index,
                    text,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    self.source.source_id,
                    snapshot_id,
                    document_id,
                    chunk_index,
                    text,
                    "{}",
                ),
            )
            row = cast(
                tuple[int] | None,
                self.connection.execute(
                    "SELECT rowid FROM chunks WHERE chunk_id = ?",
                    (chunk_id,),
                ).fetchone(),
            )
            if row is None:
                self.fail("expected chunk rowid")
            _ = self.connection.execute(
                "INSERT INTO chunk_fts(rowid, chunk_id, text) VALUES (?, ?, ?)",
                (row[0], chunk_id, text),
            )
        self.connection.commit()
        if active:
            self.store.activate_snapshot(self.source.source_id, snapshot_id)

    def test_query_filters_results_to_active_snapshots_only(self) -> None:
        engine = self._make_engine()
        self._insert_snapshot_with_chunks(
            "snapshot-stale",
            active=False,
            status=SnapshotStatus.STALE,
            document_locator="https://docs.example.com/docs/stale",
            chunks=["stale lexical result should stay hidden"],
        )
        self._insert_snapshot_with_chunks(
            "snapshot-active",
            active=True,
            status=SnapshotStatus.INDEXED,
            document_locator="https://docs.example.com/docs/active",
            chunks=["active lexical result should be returned"],
        )

        hits = engine.query("lexical result", limit=10)

        self.assertEqual([hit.snapshot_id for hit in hits], ["snapshot-active"])
        self.assertEqual(
            [hit.text for hit in hits], ["active lexical result should be returned"]
        )

    def test_query_keeps_stale_snapshots_from_leaking_after_rotation(self) -> None:
        engine = self._make_engine()
        self._insert_snapshot_with_chunks(
            "snapshot-old",
            active=False,
            status=SnapshotStatus.STALE,
            document_locator="https://docs.example.com/docs/guide/old",
            chunks=["rotation contract text from stale snapshot"],
        )
        self._insert_snapshot_with_chunks(
            "snapshot-new",
            active=True,
            status=SnapshotStatus.INDEXED,
            document_locator="https://docs.example.com/docs/guide/new",
            chunks=["rotation contract text from active snapshot"],
        )

        hits = engine.query("rotation contract text", limit=10)

        self.assertEqual([hit.chunk_id for hit in hits], ["snapshot-new-doc-0-chunk-0"])
        self.assertNotIn("snapshot-old", [hit.snapshot_id for hit in hits])

    def test_query_respects_limit_with_deterministic_chunk_order(self) -> None:
        engine = self._make_engine()
        self._insert_snapshot_with_chunks(
            "snapshot-active",
            active=True,
            status=SnapshotStatus.INDEXED,
            document_locator="https://docs.example.com/docs/guide",
            chunks=[
                "deterministic lexical ordering first",
                "deterministic lexical ordering second",
                "deterministic lexical ordering third",
            ],
        )

        hits = engine.query("deterministic lexical ordering", limit=2)

        self.assertEqual(
            [hit.chunk_id for hit in hits],
            [
                "snapshot-active-doc-0-chunk-0",
                "snapshot-active-doc-0-chunk-1",
            ],
        )
        self.assertEqual([hit.chunk_index for hit in hits], [0, 1])

    def test_reindex_snapshot_creates_multiple_chunks_from_structured_text(
        self,
    ) -> None:
        engine = self._make_engine()
        snapshot = Snapshot(
            snapshot_id="snapshot-structured",
            source_id=self.source.source_id,
            status=SnapshotStatus.INDEXED,
            content_hash="hash-structured",
            is_active=True,
        )
        self.store.insert_snapshot(snapshot)
        documents = self.store.replace_snapshot_documents(
            snapshot.snapshot_id,
            self.source.source_id,
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/guide",
                    resolved_locator="https://docs.example.com/docs/guide",
                    canonical_locator="https://docs.example.com/docs/guide",
                    title="Guide",
                    content_hash="doc-hash-structured",
                    metadata={
                        "structured_content": [
                            {"kind": "heading", "level": 1, "text": "Intro"},
                            {"kind": "paragraph", "text": "Alpha paragraph."},
                            {"kind": "heading", "level": 2, "text": "Setup"},
                            {"kind": "paragraph", "text": "Beta paragraph."},
                        ]
                    },
                )
            ],
        )
        self.store.activate_snapshot(self.source.source_id, snapshot.snapshot_id)

        engine.reindex_snapshot(self.source, snapshot, documents)

        hits = engine.query("paragraph", limit=10)
        self.assertEqual(len(hits), 2)
        self.assertEqual([hit.chunk_index for hit in hits], [0, 1])
        self.assertIn("Guide > Intro", hits[0].text)
        self.assertIn("Guide > Intro > Setup", hits[1].text)


if __name__ == "__main__":
    _ = unittest.main()

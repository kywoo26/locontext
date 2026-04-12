from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from click.testing import CliRunner

from locontext.cli.main import main
from locontext.domain.models import (
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


class QueryCommandContractTest(unittest.TestCase):
    runner: CliRunner  # pyright: ignore[reportUninitializedInstanceVariable]

    def setUp(self) -> None:  # pyright: ignore[reportImplicitOverride]
        super().setUp()
        self.runner = CliRunner()

    def _seed_query_state(self) -> None:
        data_dir = Path(".locontext")
        data_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(data_dir / "locontext.db")
        try:
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
            stale_snapshot = Snapshot(
                snapshot_id="snapshot-stale",
                source_id=source.source_id,
                status=SnapshotStatus.STALE,
                content_hash="hash-stale",
                is_active=False,
            )
            active_snapshot = Snapshot(
                snapshot_id="snapshot-active",
                source_id=source.source_id,
                status=SnapshotStatus.INDEXED,
                content_hash="hash-active",
                is_active=True,
            )
            store.insert_snapshot(stale_snapshot)
            _ = store.replace_snapshot_documents(
                stale_snapshot.snapshot_id,
                source.source_id,
                [
                    DiscoveredDocument(
                        requested_locator="https://docs.example.com/docs/stale",
                        resolved_locator="https://docs.example.com/docs/stale",
                        canonical_locator="https://docs.example.com/docs/stale",
                        title="Stale",
                        content_hash="doc-hash-stale",
                    )
                ],
            )
            store.insert_snapshot(active_snapshot)
            _ = store.replace_snapshot_documents(
                active_snapshot.snapshot_id,
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
            _ = connection.execute(
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
                    "snapshot-stale-doc-0-chunk-0",
                    source.source_id,
                    stale_snapshot.snapshot_id,
                    "snapshot-stale-doc-0",
                    0,
                    "shared query text from stale content",
                    "{}",
                ),
            )
            row = connection.execute(
                "SELECT rowid FROM chunks WHERE chunk_id = ?",
                ("snapshot-stale-doc-0-chunk-0",),
            ).fetchone()
            if row is None:
                self.fail("expected stale chunk rowid")
            _ = connection.execute(
                "INSERT INTO chunk_fts(rowid, chunk_id, text) VALUES (?, ?, ?)",
                (
                    row[0],
                    "snapshot-stale-doc-0-chunk-0",
                    "shared query text from stale content",
                ),
            )
            active_chunks = [
                "shared query text from active content",
                "shared query text second active hit",
            ]
            for chunk_index, text in enumerate(active_chunks):
                chunk_id = f"snapshot-active-doc-0-chunk-{chunk_index}"
                _ = connection.execute(
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
                        source.source_id,
                        active_snapshot.snapshot_id,
                        "snapshot-active-doc-0",
                        chunk_index,
                        text,
                        "{}",
                    ),
                )
                active_row = connection.execute(
                    "SELECT rowid FROM chunks WHERE chunk_id = ?",
                    (chunk_id,),
                ).fetchone()
                if active_row is None:
                    self.fail("expected active chunk rowid")
                _ = connection.execute(
                    "INSERT INTO chunk_fts(rowid, chunk_id, text) VALUES (?, ?, ?)",
                    (active_row[0], chunk_id, text),
                )
            connection.commit()
            store.activate_snapshot(source.source_id, active_snapshot.snapshot_id)
        finally:
            connection.close()

    def test_query_reports_stable_empty_state(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(
                main, ["query", "definitely-no-hit", "--limit", "5"]
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, "No query results.\n")

    def test_query_help_is_available(self) -> None:
        result = self.runner.invoke(main, ["query", "--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Usage:", result.output)
        self.assertIn("--limit INTEGER", result.output)

    def test_query_reports_stable_success_output_for_active_hits_only(self) -> None:
        with self.runner.isolated_filesystem():
            self._seed_query_state()

            result = self.runner.invoke(
                main, ["query", "shared query text", "--limit", "1"]
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output.strip().splitlines(),
            [
                "1. https://docs.example.com/docs",
                "   document: https://docs.example.com/docs/guide",
                "   chunk: shared query text from active content",
            ],
        )


if __name__ == "__main__":
    _ = unittest.main()

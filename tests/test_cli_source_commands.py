from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from click.testing import CliRunner

from locontext.cli.main import main
from locontext.domain.models import DiscoveryOutcome, Snapshot, Source


class _EmptyDiscoveryProvider:
    def discover(self, source: Source) -> DiscoveryOutcome:
        _ = source
        return DiscoveryOutcome(documents=[])


class _RecordingIndexingEngine:
    def __init__(self) -> None:
        self.reindex_calls: list[tuple[str, str, int]] = []

    def reindex_snapshot(
        self,
        source: Source,
        snapshot: Snapshot,
        documents: list[object],
    ) -> None:
        self.reindex_calls.append(
            (source.source_id, snapshot.snapshot_id, len(documents))
        )

    def remove_source(self, _source_id: str) -> None:
        return None


class SourceCommandTest(unittest.TestCase):
    runner: CliRunner = CliRunner()

    def _snapshot_id(self, source_id: str) -> str | None:
        with sqlite3.connect(".locontext/locontext.db") as connection:
            row = cast(
                tuple[str | None] | None,
                connection.execute(
                    "SELECT active_snapshot_id FROM sources WHERE source_id = ?",
                    (source_id,),
                ).fetchone(),
            )
        if row is None:
            self.fail("expected a stored source row")
        return row[0]

    def test_source_add_creates_default_local_db(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(
                main,
                ["source", "add", "https://docs.example.com/docs?utm_source=x#intro"],
            )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("created source:", result.output)
            self.assertIn(
                "canonical locator: https://docs.example.com/docs", result.output
            )
            self.assertTrue(Path(".locontext/locontext.db").exists())

    def test_source_add_is_idempotent_for_equivalent_urls(self) -> None:
        with self.runner.isolated_filesystem():
            first = self.runner.invoke(
                main,
                ["source", "add", "https://docs.example.com/docs?utm_source=x#intro"],
            )
            second = self.runner.invoke(
                main,
                ["source", "add", "https://docs.example.com/docs"],
            )

            self.assertEqual(first.exit_code, 0)
            self.assertEqual(second.exit_code, 0)
            self.assertIn("created source:", first.output)
            self.assertIn("existing source:", second.output)

    def test_source_list_reports_empty_state(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["source", "list"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, "No sources registered.\n")

    def test_source_list_shows_registered_sources_in_stable_order(self) -> None:
        with self.runner.isolated_filesystem():
            _ = self.runner.invoke(
                main, ["source", "add", "https://docs.example.com/docs/beta"]
            )
            _ = self.runner.invoke(
                main, ["source", "add", "https://docs.example.com/docs/alpha"]
            )

            result = self.runner.invoke(main, ["source", "list"])

            self.assertEqual(result.exit_code, 0)
            lines = result.output.strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn("https://docs.example.com/docs/alpha", lines[0])
            self.assertIn("https://docs.example.com/docs/beta", lines[1])

    def test_source_remove_reports_removed_source(self) -> None:
        with self.runner.isolated_filesystem():
            add_result = self.runner.invoke(
                main, ["source", "add", "https://docs.example.com/docs"]
            )
            self.assertEqual(add_result.exit_code, 0)
            source_id = add_result.output.splitlines()[0].split()[-1]

            result = self.runner.invoke(main, ["source", "remove", source_id])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, f"removed source: {source_id}\n")

    def test_source_remove_reports_missing_source(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["source", "remove", "missing-id"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, "source not found: missing-id\n")

    def test_source_remove_help_works(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["source", "remove", "--help"])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Remove a registered documentation source.", result.output)

    def test_source_status_reports_empty_state(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["source", "status"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, "No sources registered.\n")

    def test_source_status_reports_freshness_for_unrefreshed_source(self) -> None:
        with self.runner.isolated_filesystem():
            add_result = self.runner.invoke(
                main, ["source", "add", "https://docs.example.com/docs"]
            )
            self.assertEqual(add_result.exit_code, 0)

            result = self.runner.invoke(main, ["source", "status"])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("freshness=never-refreshed", result.output)

    def test_source_show_reports_missing_source(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["source", "show", "missing-id"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, "source not found: missing-id\n")

    def _snapshot_fetched_at(self, snapshot_id: str) -> str:
        with sqlite3.connect(".locontext/locontext.db") as connection:
            row = cast(
                tuple[str] | None,
                connection.execute(
                    "SELECT fetched_at FROM snapshots WHERE snapshot_id = ?",
                    (snapshot_id,),
                ).fetchone(),
            )
        if row is None:
            self.fail("expected a stored snapshot row")
        return row[0]

    def test_source_show_reports_active_zero_document_snapshot(self) -> None:
        with self.runner.isolated_filesystem():
            add_result = self.runner.invoke(
                main, ["source", "add", "https://docs.example.com/docs"]
            )
            self.assertEqual(add_result.exit_code, 0)
            source_id = add_result.output.splitlines()[0].split()[-1]
            provider = _EmptyDiscoveryProvider()
            engine = _RecordingIndexingEngine()

            with (
                patch(
                    "locontext.app.refresh._default_discovery_provider",
                    return_value=provider,
                ),
                patch(
                    "locontext.app.refresh._default_indexing_engine",
                    return_value=engine,
                ),
            ):
                refresh_result = self.runner.invoke(
                    main, ["source", "refresh", source_id]
                )

            self.assertEqual(refresh_result.exit_code, 0)
            snapshot_id = self._snapshot_id(source_id)
            self.assertIsNotNone(snapshot_id)
            snapshot_id = cast(str, snapshot_id)
            fetched_at = self._snapshot_fetched_at(snapshot_id)

            result = self.runner.invoke(main, ["source", "show", source_id])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.output.strip().splitlines(),
                [
                    f"source_id: {source_id}",
                    "canonical_locator: https://docs.example.com/docs",
                    "docset_root: https://docs.example.com",
                    f"active_snapshot_id: {snapshot_id}",
                    "snapshot_status: indexed",
                    "document_count: 0",
                    "chunk_count: 0",
                    f"fetched_at: {fetched_at}",
                    "freshness: unhealthy-empty",
                    "freshness_reason: zero documents in active snapshot",
                    "etag: none",
                    "last_modified: none",
                ],
            )

    def test_source_add_honors_custom_data_dir(self) -> None:
        with self.runner.isolated_filesystem():
            Path("locontext.toml").write_text(
                'data_dir = "custom-state"\n', encoding="utf-8"
            )

            result = self.runner.invoke(
                main, ["source", "add", "https://docs.example.com/docs"]
            )

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(Path("custom-state/locontext.db").exists())
            connection = sqlite3.connect("custom-state/locontext.db")
            try:
                row = connection.execute("SELECT COUNT(*) FROM sources").fetchone()
            finally:
                connection.close()
            self.assertEqual(row[0], 1)


if __name__ == "__main__":
    unittest.main()

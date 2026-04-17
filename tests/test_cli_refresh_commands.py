from __future__ import annotations

import sqlite3
import unittest
from hashlib import sha256
from typing import cast
from unittest.mock import patch

from click.testing import CliRunner

from locontext.cli.main import main
from locontext.domain.models import (
    DiscoveredDocument,
    DiscoveryOutcome,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


class _StaticDiscoveryProvider:
    title: str
    content_hash: str

    def __init__(self, title: str = "Intro", content_hash: str = "hash-1") -> None:
        self.title = title
        self.content_hash = content_hash

    def discover(self, source: Source) -> DiscoveryOutcome:
        resolved_locator = source.resolved_locator or source.canonical_locator
        return DiscoveryOutcome(
            documents=[
                DiscoveredDocument(
                    requested_locator=source.requested_locator,
                    resolved_locator=resolved_locator,
                    canonical_locator=source.canonical_locator,
                    title=self.title,
                    content_hash=self.content_hash,
                )
            ]
        )


class _EmptyDiscoveryProvider:
    def discover(self, source: Source) -> DiscoveryOutcome:
        _ = source
        return DiscoveryOutcome(documents=[])


class _StaticOutcomeDiscoveryProvider:
    def __init__(self, outcome: DiscoveryOutcome) -> None:
        self.outcome = outcome

    def discover(self, source: Source) -> DiscoveryOutcome:
        _ = source
        return self.outcome


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


def _legacy_manifest_hash(documents: list[DiscoveredDocument]) -> str:
    payload = "\n".join(
        "|".join(
            [
                document.requested_locator,
                document.resolved_locator,
                document.canonical_locator,
                document.title or "",
                document.content_hash or "",
            ]
        )
        for document in documents
    )
    return sha256(payload.encode("utf-8")).hexdigest()


class SourceRefreshCommandTest(unittest.TestCase):
    runner: CliRunner = CliRunner()

    def _seed_source(self) -> str:
        result = self.runner.invoke(
            main,
            ["source", "add", "https://docs.example.com/docs?utm_source=x#intro"],
        )
        self.assertEqual(result.exit_code, 0)
        with sqlite3.connect(".locontext/locontext.db") as connection:
            row = cast(
                tuple[str] | None,
                connection.execute(
                    "SELECT source_id FROM sources ORDER BY canonical_locator ASC"
                ).fetchone(),
            )
        if row is None:
            self.fail("expected a registered source")
        return row[0]

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

    def test_source_refresh_creates_active_snapshot_and_reports_changed(self) -> None:
        with self.runner.isolated_filesystem():
            source_id = self._seed_source()
            provider = _StaticDiscoveryProvider()
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
                result = self.runner.invoke(main, ["source", "refresh", source_id])

            self.assertEqual(result.exit_code, 0)
            snapshot_id = self._snapshot_id(source_id)
            self.assertIsNotNone(snapshot_id)
            snapshot_id = cast(str, snapshot_id)
            self.assertEqual(
                result.output.strip().splitlines(),
                [
                    f"refreshed source: {source_id}",
                    "result: changed",
                    "freshness: current",
                    f"active snapshot: {snapshot_id}",
                    "documents: 1",
                ],
            )
            with sqlite3.connect(".locontext/locontext.db") as connection:
                row = cast(
                    tuple[int, str] | None,
                    connection.execute(
                        "SELECT is_active, status FROM snapshots WHERE snapshot_id = ?",
                        (snapshot_id,),
                    ).fetchone(),
                )
            if row is None:
                self.fail("expected a stored snapshot row")
            self.assertEqual(row[0], 1)
            self.assertEqual(row[1], "indexed")
            self.assertEqual(engine.reindex_calls, [(source_id, snapshot_id, 1)])

    def test_source_refresh_reports_unhealthy_empty_when_no_documents_are_found(
        self,
    ) -> None:
        with self.runner.isolated_filesystem():
            source_id = self._seed_source()
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
                result = self.runner.invoke(main, ["source", "refresh", source_id])

            self.assertEqual(result.exit_code, 0)
            snapshot_id = self._snapshot_id(source_id)
            self.assertIsNotNone(snapshot_id)
            snapshot_id = cast(str, snapshot_id)
            self.assertEqual(
                result.output.strip().splitlines(),
                [
                    f"refreshed source: {source_id}",
                    "result: changed",
                    "freshness: unhealthy-empty",
                    f"active snapshot: {snapshot_id}",
                    "documents: 0",
                ],
            )
            self.assertEqual(engine.reindex_calls, [(source_id, snapshot_id, 0)])

    def test_source_refresh_reports_unchanged_when_manifest_matches(self) -> None:
        with self.runner.isolated_filesystem():
            source_id = self._seed_source()
            provider = _StaticDiscoveryProvider()
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
                first = self.runner.invoke(main, ["source", "refresh", source_id])
                second = self.runner.invoke(main, ["source", "refresh", source_id])

            self.assertEqual(first.exit_code, 0)
            self.assertEqual(second.exit_code, 0)
            snapshot_id = self._snapshot_id(source_id)
            self.assertIsNotNone(snapshot_id)
            snapshot_id = cast(str, snapshot_id)
            self.assertEqual(
                second.output.strip().splitlines(),
                [
                    f"refreshed source: {source_id}",
                    "result: unchanged",
                    "freshness: current",
                    f"active snapshot: {snapshot_id}",
                    "documents: 1",
                ],
            )
            self.assertEqual(engine.reindex_calls, [(source_id, snapshot_id, 1)])

    def test_source_refresh_reprocesses_legacy_github_snapshot(self) -> None:
        with self.runner.isolated_filesystem():
            source_id = self._seed_source()
            github_source = Source(
                source_id=source_id,
                source_kind=SourceKind.WEB,
                requested_locator="https://github.com/example/project",
                resolved_locator="https://github.com/example/project",
                canonical_locator="https://github.com/example/project",
                docset_root="https://github.com/example/project",
            )
            readme = DiscoveredDocument(
                requested_locator="https://github.com/example/project",
                resolved_locator="https://github.com/example/project",
                canonical_locator="https://github.com/example/project",
                title="README",
                content_hash="hash-readme",
            )
            management = DiscoveredDocument(
                requested_locator="https://github.com/example/project/issues",
                resolved_locator="https://github.com/example/project/issues",
                canonical_locator="https://github.com/example/project/issues",
                title="Issues",
                content_hash="hash-issues",
            )
            legacy_snapshot = Snapshot(
                snapshot_id="legacy-github-snapshot",
                source_id=source_id,
                status=SnapshotStatus.INDEXED,
                fetched_at="2025-01-01T00:00:00+00:00",
                content_hash=_legacy_manifest_hash([readme]),
                is_active=True,
            )
            with sqlite3.connect(".locontext/locontext.db") as connection:
                store = SQLiteStore(connection)
                store.upsert_source(github_source)
                store.insert_snapshot(legacy_snapshot)
                _ = store.replace_snapshot_documents(
                    legacy_snapshot.snapshot_id,
                    github_source.source_id,
                    [readme, management],
                )
                store.activate_snapshot(source_id, legacy_snapshot.snapshot_id)
            provider = _StaticOutcomeDiscoveryProvider(
                DiscoveryOutcome(documents=[readme, management])
            )
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
                result = self.runner.invoke(main, ["source", "refresh", source_id])

            self.assertEqual(result.exit_code, 0)
            snapshot_id = self._snapshot_id(source_id)
            self.assertIsNotNone(snapshot_id)
            snapshot_id = cast(str, snapshot_id)
            self.assertNotEqual(snapshot_id, legacy_snapshot.snapshot_id)
            self.assertEqual(
                result.output.strip().splitlines(),
                [
                    f"refreshed source: {source_id}",
                    "result: changed",
                    "freshness: current",
                    f"active snapshot: {snapshot_id}",
                    "documents: 2",
                ],
            )
            with sqlite3.connect(".locontext/locontext.db") as connection:
                row = cast(
                    tuple[int, str] | None,
                    connection.execute(
                        "SELECT is_active, status FROM snapshots WHERE snapshot_id = ?",
                        (snapshot_id,),
                    ).fetchone(),
                )
            if row is None:
                self.fail("expected a stored snapshot row")
            self.assertEqual(row[0], 1)
            self.assertEqual(row[1], "indexed")
            self.assertEqual(engine.reindex_calls, [(source_id, snapshot_id, 2)])

    def test_source_reindex_uses_active_snapshot_without_discovery(self) -> None:
        with self.runner.isolated_filesystem():
            source_id = self._seed_source()
            provider = _StaticDiscoveryProvider()
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
                first = self.runner.invoke(main, ["source", "refresh", source_id])

            self.assertEqual(first.exit_code, 0)
            snapshot_id = self._snapshot_id(source_id)
            self.assertIsNotNone(snapshot_id)
            snapshot_id = cast(str, snapshot_id)

            with (
                patch(
                    "locontext.app.refresh._default_discovery_provider",
                    side_effect=AssertionError("discovery should not run"),
                ),
                patch(
                    "locontext.app.refresh._default_indexing_engine",
                    return_value=engine,
                ),
            ):
                result = self.runner.invoke(main, ["source", "reindex", source_id])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.output.strip().splitlines(),
                [
                    f"reindexed source: {source_id}",
                    f"active snapshot: {snapshot_id}",
                    "documents: 1",
                ],
            )
            self.assertEqual(
                engine.reindex_calls,
                [(source_id, snapshot_id, 1), (source_id, snapshot_id, 1)],
            )


if __name__ == "__main__":
    _ = unittest.main()

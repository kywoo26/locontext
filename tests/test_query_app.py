from __future__ import annotations

import sqlite3
import unittest
from importlib import import_module
from typing import Protocol, cast
from unittest.mock import patch

from locontext.domain.models import (
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


class _QueryHitLike(Protocol):
    source_id: str
    snapshot_id: str
    document_id: str
    chunk_id: str
    chunk_index: int
    text: str


class _QueryEnvelopeHitLike(Protocol):
    document_locator: str


class _QueryEnvelopeLike(Protocol):
    query_text: str
    limit: int
    source_id: str | None
    hit_count: int
    hits: list[_QueryEnvelopeHitLike]


class _QueryLocalJson(Protocol):
    def __call__(
        self,
        store: SQLiteStore,
        text: str,
        *,
        limit: int,
        source_id: str | None = None,
    ) -> _QueryEnvelopeLike: ...


class _QueryLocal(Protocol):
    def __call__(
        self,
        store: SQLiteStore,
        text: str,
        *,
        limit: int,
        source_id: str | None = None,
    ) -> list[_QueryHitLike]: ...


class QueryAppContractTest(unittest.TestCase):
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

    def _query_local(
        self,
        text: str,
        limit: int,
        *,
        source_id: str | None = None,
    ) -> list[_QueryHitLike]:
        try:
            module = import_module("locontext.app.query")
        except ModuleNotFoundError as exc:
            self.fail(f"expected locontext.app.query module: {exc}")

        query_local = cast(_QueryLocal | None, getattr(module, "query_local", None))
        if query_local is None:
            self.fail("expected locontext.app.query.query_local")
        return query_local(self.store, text, limit=limit, source_id=source_id)

    def _query_local_json(
        self,
        text: str,
        limit: int,
        *,
        source_id: str | None = None,
    ) -> _QueryEnvelopeLike:
        try:
            module = import_module("locontext.app.query")
        except ModuleNotFoundError as exc:
            self.fail(f"expected locontext.app.query module: {exc}")

        query_local_json = cast(
            _QueryLocalJson | None, getattr(module, "query_local_json", None)
        )
        if query_local_json is None:
            self.fail("expected locontext.app.query.query_local_json")
        return query_local_json(self.store, text, limit=limit, source_id=source_id)

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

    def _seed_github_repo_snapshot(self) -> None:
        snapshot = Snapshot(
            snapshot_id="snapshot-github",
            source_id=self.source.source_id,
            status=SnapshotStatus.INDEXED,
            content_hash="hash-snapshot-github",
            is_active=True,
        )
        self.store.insert_snapshot(snapshot)
        discovered_documents = [
            DiscoveredDocument(
                requested_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/README.md",
                resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/README.md",
                canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/README.md",
                title="README",
                content_hash="doc-hash-readme",
            ),
            DiscoveredDocument(
                requested_locator="https://github.com/code-yeongyu/oh-my-openagent/tree/main/docs/guide.md",
                resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/tree/main/docs/guide.md",
                canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/tree/main/docs/guide.md",
                title="Guide",
                content_hash="doc-hash-guide",
            ),
            DiscoveredDocument(
                requested_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/examples/install-api.md",
                resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/examples/install-api.md",
                canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/examples/install-api.md",
                title="install-api.md",
                content_hash="doc-hash-install-api",
            ),
            DiscoveredDocument(
                requested_locator="https://github.com/code-yeongyu/oh-my-openagent/wiki",
                resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/wiki",
                canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/wiki",
                title="Wiki",
                content_hash="doc-hash-wiki",
            ),
            DiscoveredDocument(
                requested_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
                resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
                canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
                title="AGENTS.md",
                content_hash="doc-hash-agents",
            ),
            DiscoveredDocument(
                requested_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/CLAUDE.md",
                resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/CLAUDE.md",
                canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/CLAUDE.md",
                title="CLAUDE.md",
                content_hash="doc-hash-claude",
            ),
            DiscoveredDocument(
                requested_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/llms.txt",
                resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/llms.txt",
                canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/llms.txt",
                title="llms.txt",
                content_hash="doc-hash-llms",
            ),
            DiscoveredDocument(
                requested_locator="https://github.com/code-yeongyu/oh-my-openagent/releases",
                resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/releases",
                canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/releases",
                title="releases",
                content_hash="doc-hash-releases",
            ),
            DiscoveredDocument(
                requested_locator="https://github.com/code-yeongyu/oh-my-openagent/issues",
                resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/issues",
                canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/issues",
                title="issues",
                content_hash="doc-hash-issues",
            ),
            DiscoveredDocument(
                requested_locator="https://github.com/code-yeongyu/oh-my-openagent/pulls",
                resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/pulls",
                canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/pulls",
                title="pulls",
                content_hash="doc-hash-pulls",
            ),
            DiscoveredDocument(
                requested_locator="https://github.com/code-yeongyu/oh-my-openagent/compare/main...HEAD",
                resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/compare/main...HEAD",
                canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/compare/main...HEAD",
                title="compare",
                content_hash="doc-hash-compare",
            ),
        ]
        stored_documents = self.store.replace_snapshot_documents(
            snapshot.snapshot_id,
            self.source.source_id,
            discovered_documents,
        )
        chunk_texts = {
            "https://github.com/code-yeongyu/oh-my-openagent/blob/main/README.md": "README install api configuration how to use",
            "https://github.com/code-yeongyu/oh-my-openagent/tree/main/docs/guide.md": "Docs configuration install api",
            "https://github.com/code-yeongyu/oh-my-openagent/blob/main/examples/install-api.md": "Examples install api walkthrough",
            "https://github.com/code-yeongyu/oh-my-openagent/wiki": "Wiki how to use install api",
            "https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md": "AGENTS agent command workflow prompt instructions how to work in this repo",
            "https://github.com/code-yeongyu/oh-my-openagent/blob/main/CLAUDE.md": "CLAUDE workflow prompt instructions how to work in this repo",
            "https://github.com/code-yeongyu/oh-my-openagent/blob/main/llms.txt": "llms prompt instructions how to work in this repo",
            "https://github.com/code-yeongyu/oh-my-openagent/releases": "agent agent agent command command workflow prompt instructions how to work in this repo release notes open issues pull request compare versions",
            "https://github.com/code-yeongyu/oh-my-openagent/issues": "Open issues release notes",
            "https://github.com/code-yeongyu/oh-my-openagent/pulls": "Pull request release notes",
            "https://github.com/code-yeongyu/oh-my-openagent/compare/main...HEAD": "Compare versions release notes",
        }
        for index, document in enumerate(stored_documents):
            text = chunk_texts[document.canonical_locator]
            chunk_id = f"{document.document_id}-chunk-{index}"
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
                    snapshot.snapshot_id,
                    document.document_id,
                    0,
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
        self.store.activate_snapshot(self.source.source_id, snapshot.snapshot_id)

    def test_query_local_uses_stored_content_without_network_access(self) -> None:
        self._insert_snapshot_with_chunks(
            "snapshot-active",
            active=True,
            status=SnapshotStatus.INDEXED,
            document_locator="https://docs.example.com/docs/intro",
            chunks=["local only query contract"],
        )

        with patch(
            "socket.create_connection",
            side_effect=AssertionError("query must stay local"),
        ):
            hits = self._query_local("local only query contract", limit=5)

        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual(hit.source_id, self.source.source_id)
        self.assertEqual(hit.snapshot_id, "snapshot-active")
        self.assertEqual(hit.document_id, "snapshot-active-doc-0")
        self.assertEqual(hit.chunk_index, 0)
        self.assertEqual(hit.text, "local only query contract")

    def test_query_local_searches_active_snapshots_only(self) -> None:
        self._insert_snapshot_with_chunks(
            "snapshot-stale",
            active=False,
            status=SnapshotStatus.STALE,
            document_locator="https://docs.example.com/docs/stale",
            chunks=["shared contract phrase from stale content"],
        )
        self._insert_snapshot_with_chunks(
            "snapshot-active",
            active=True,
            status=SnapshotStatus.INDEXED,
            document_locator="https://docs.example.com/docs/active",
            chunks=["shared contract phrase from active content"],
        )

        hits = self._query_local("shared contract phrase", limit=5)

        self.assertEqual([hit.snapshot_id for hit in hits], ["snapshot-active"])
        self.assertEqual(
            [hit.chunk_id for hit in hits], ["snapshot-active-doc-0-chunk-0"]
        )

    def test_query_local_accepts_plain_text_and_respects_limit(self) -> None:
        self._insert_snapshot_with_chunks(
            "snapshot-active",
            active=True,
            status=SnapshotStatus.INDEXED,
            document_locator="https://docs.example.com/docs/guide",
            chunks=[
                "plain text query contract",
                "plain text query contract second chunk",
                "plain text query contract third chunk",
            ],
        )

        hits = self._query_local("plain text query contract", limit=2)

        self.assertEqual(len(hits), 2)
        self.assertEqual([hit.chunk_index for hit in hits], [0, 1])
        self.assertEqual(
            [hit.text for hit in hits],
            [
                "plain text query contract",
                "plain text query contract second chunk",
            ],
        )

    def test_query_local_returns_chunk_level_results_for_structured_content(
        self,
    ) -> None:
        self._insert_snapshot_with_chunks(
            "snapshot-active",
            active=True,
            status=SnapshotStatus.INDEXED,
            document_locator="https://docs.example.com/docs/guide",
            chunks=[
                "Guide > Intro Alpha paragraph",
                "Guide > Intro > Setup Beta paragraph",
            ],
        )

        hits = self._query_local("paragraph", limit=10)

        self.assertEqual(len(hits), 2)
        self.assertEqual([hit.chunk_index for hit in hits], [0, 1])
        self.assertIn("Guide > Intro", hits[0].text)
        self.assertIn("Guide > Intro > Setup", hits[1].text)

    def test_query_local_passes_through_source_filter(self) -> None:
        self._insert_snapshot_with_chunks(
            "snapshot-active",
            active=True,
            status=SnapshotStatus.INDEXED,
            document_locator="https://docs.example.com/docs/guide",
            chunks=["shared filter term from source one"],
        )

        hits = self._query_local(
            "shared filter term",
            limit=10,
            source_id=self.source.source_id,
        )

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].source_id, self.source.source_id)

    def test_query_local_json_returns_stable_envelope(self) -> None:
        self._insert_snapshot_with_chunks(
            "snapshot-active",
            active=True,
            status=SnapshotStatus.INDEXED,
            document_locator="https://docs.example.com/docs/guide",
            chunks=["shared machine query term"],
        )

        result = self._query_local_json("shared machine query term", limit=5)

        self.assertEqual(result.query_text, "shared machine query term")
        self.assertEqual(result.limit, 5)
        self.assertIsNone(result.source_id)
        self.assertEqual(result.hit_count, 1)

    def test_query_local_orders_github_repo_intents_exactly(self) -> None:
        self._seed_github_repo_snapshot()

        expectations = {
            "install api": [
                "https://github.com/code-yeongyu/oh-my-openagent/blob/main/README.md",
                "https://github.com/code-yeongyu/oh-my-openagent/tree/main/docs/guide.md",
                "https://github.com/code-yeongyu/oh-my-openagent/blob/main/examples/install-api.md",
                "https://github.com/code-yeongyu/oh-my-openagent/wiki",
            ],
            "release notes": [
                "https://github.com/code-yeongyu/oh-my-openagent/releases",
                "https://github.com/code-yeongyu/oh-my-openagent/issues",
                "https://github.com/code-yeongyu/oh-my-openagent/pulls",
                "https://github.com/code-yeongyu/oh-my-openagent/compare/main...HEAD",
            ],
        }

        for query_text, expected_locators in expectations.items():
            with self.subTest(query_text=query_text):
                result = self._query_local_json(query_text, limit=5)
                self.assertEqual(
                    [hit.document_locator for hit in result.hits], expected_locators
                )

    def test_query_local_boosts_guidance_before_releases_for_repo_operational_intent(
        self,
    ) -> None:
        self._seed_github_repo_snapshot()

        result = self._query_local_json("agent command", limit=5)

        self.assertEqual(
            [hit.document_locator for hit in result.hits],
            [
                "https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
                "https://github.com/code-yeongyu/oh-my-openagent/releases",
            ],
        )

    def test_query_local_treats_instructions_as_repo_operational_intent(self) -> None:
        self._seed_github_repo_snapshot()

        result = self._query_local_json("instructions", limit=5)

        self.assertEqual(
            [hit.document_locator for hit in result.hits],
            [
                "https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
                "https://github.com/code-yeongyu/oh-my-openagent/blob/main/CLAUDE.md",
                "https://github.com/code-yeongyu/oh-my-openagent/blob/main/llms.txt",
                "https://github.com/code-yeongyu/oh-my-openagent/releases",
            ],
        )

    def test_query_local_treats_how_to_work_phrase_as_repo_operational_intent(
        self,
    ) -> None:
        self._seed_github_repo_snapshot()

        result = self._query_local_json("how to work in this repo", limit=5)

        self.assertEqual(
            [hit.document_locator for hit in result.hits],
            [
                "https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
                "https://github.com/code-yeongyu/oh-my-openagent/blob/main/CLAUDE.md",
                "https://github.com/code-yeongyu/oh-my-openagent/blob/main/llms.txt",
                "https://github.com/code-yeongyu/oh-my-openagent/releases",
            ],
        )

    def test_query_local_does_not_treat_repo_file_named_issues_as_management(
        self,
    ) -> None:
        snapshot = Snapshot(
            snapshot_id="snapshot-github-issues-file",
            source_id=self.source.source_id,
            status=SnapshotStatus.INDEXED,
            content_hash="hash-snapshot-github-issues-file",
            is_active=True,
        )
        self.store.insert_snapshot(snapshot)
        stored_documents = self.store.replace_snapshot_documents(
            snapshot.snapshot_id,
            self.source.source_id,
            [
                DiscoveredDocument(
                    requested_locator="https://github.com/code-yeongyu/oh-my-openagent/releases",
                    resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/releases",
                    canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/releases",
                    title="releases",
                    content_hash="doc-hash-releases",
                ),
                DiscoveredDocument(
                    requested_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/issues.md",
                    resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/issues.md",
                    canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/issues.md",
                    title="issues.md",
                    content_hash="doc-hash-issues-md",
                ),
            ],
        )
        chunk_texts = {
            "https://github.com/code-yeongyu/oh-my-openagent/releases": "release notes official project releases",
            "https://github.com/code-yeongyu/oh-my-openagent/blob/main/issues.md": "release notes from an issues document inside the repo",
        }
        for index, document in enumerate(stored_documents):
            text = chunk_texts[document.canonical_locator]
            chunk_id = f"{document.document_id}-chunk-{index}"
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
                    snapshot.snapshot_id,
                    document.document_id,
                    0,
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
        self.store.activate_snapshot(self.source.source_id, snapshot.snapshot_id)

        result = self._query_local_json("release notes", limit=5)

        self.assertEqual(
            [hit.document_locator for hit in result.hits],
            [
                "https://github.com/code-yeongyu/oh-my-openagent/releases",
                "https://github.com/code-yeongyu/oh-my-openagent/blob/main/issues.md",
            ],
        )


if __name__ == "__main__":
    _ = unittest.main()

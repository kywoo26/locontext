import sqlite3
from importlib import import_module
from typing import Protocol, cast

import pytest
from pytest_mock import MockerFixture

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


@pytest.fixture()
def source(store: SQLiteStore) -> Source:
    result = Source(
        source_id="source-1",
        source_kind=SourceKind.WEB,
        requested_locator="https://docs.example.com/docs",
        resolved_locator="https://docs.example.com/docs",
        canonical_locator="https://docs.example.com/docs",
        docset_root="https://docs.example.com/docs",
    )
    store.upsert_source(result)
    return result


def _query_local(
    store: SQLiteStore,
    text: str,
    limit: int,
    *,
    source_id: str | None = None,
) -> list[_QueryHitLike]:
    try:
        module = import_module("locontext.app.query")
    except ModuleNotFoundError as exc:
        raise AssertionError(f"expected locontext.app.query module: {exc}") from exc

    query_local = cast(_QueryLocal | None, getattr(module, "query_local", None))
    if query_local is None:
        raise AssertionError("expected locontext.app.query.query_local")
    return query_local(store, text, limit=limit, source_id=source_id)


def _query_local_json(
    store: SQLiteStore,
    text: str,
    limit: int,
    *,
    source_id: str | None = None,
) -> _QueryEnvelopeLike:
    try:
        module = import_module("locontext.app.query")
    except ModuleNotFoundError as exc:
        raise AssertionError(f"expected locontext.app.query module: {exc}") from exc

    query_local_json = cast(
        _QueryLocalJson | None, getattr(module, "query_local_json", None)
    )
    if query_local_json is None:
        raise AssertionError("expected locontext.app.query.query_local_json")
    return query_local_json(store, text, limit=limit, source_id=source_id)


def _insert_snapshot_with_chunks(
    connection: sqlite3.Connection,
    store: SQLiteStore,
    source: Source,
    snapshot_id: str,
    *,
    active: bool,
    status: SnapshotStatus,
    document_locator: str,
    chunks: list[str],
) -> None:
    snapshot = Snapshot(
        snapshot_id=snapshot_id,
        source_id=source.source_id,
        status=status,
        content_hash=f"hash-{snapshot_id}",
        is_active=active,
    )
    store.insert_snapshot(snapshot)
    _ = store.replace_snapshot_documents(
        snapshot_id,
        source.source_id,
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
                snapshot_id,
                document_id,
                chunk_index,
                text,
                "{}",
            ),
        )
        row = cast(
            tuple[int] | None,
            connection.execute(
                "SELECT rowid FROM chunks WHERE chunk_id = ?", (chunk_id,)
            ).fetchone(),
        )
        if row is None:
            raise AssertionError("expected chunk rowid")
        _ = connection.execute(
            "INSERT INTO chunk_fts(rowid, chunk_id, text) VALUES (?, ?, ?)",
            (row[0], chunk_id, text),
        )
    connection.commit()
    if active:
        store.activate_snapshot(source.source_id, snapshot_id)


def _seed_github_repo_snapshot(
    connection: sqlite3.Connection, store: SQLiteStore, source: Source
) -> None:
    snapshot = Snapshot(
        snapshot_id="snapshot-github",
        source_id=source.source_id,
        status=SnapshotStatus.INDEXED,
        content_hash="hash-snapshot-github",
        is_active=True,
    )
    store.insert_snapshot(snapshot)
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
    stored_documents = store.replace_snapshot_documents(
        snapshot.snapshot_id,
        source.source_id,
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
                snapshot.snapshot_id,
                document.document_id,
                0,
                text,
                "{}",
            ),
        )
        row = cast(
            tuple[int] | None,
            connection.execute(
                "SELECT rowid FROM chunks WHERE chunk_id = ?", (chunk_id,)
            ).fetchone(),
        )
        if row is None:
            raise AssertionError("expected chunk rowid")
        _ = connection.execute(
            "INSERT INTO chunk_fts(rowid, chunk_id, text) VALUES (?, ?, ?)",
            (row[0], chunk_id, text),
        )
    connection.commit()
    store.activate_snapshot(source.source_id, snapshot.snapshot_id)


def test_query_local_uses_stored_content_without_network_access(
    connection: sqlite3.Connection,
    store: SQLiteStore,
    source: Source,
    mocker: MockerFixture,
) -> None:
    _insert_snapshot_with_chunks(
        connection,
        store,
        source,
        "snapshot-active",
        active=True,
        status=SnapshotStatus.INDEXED,
        document_locator="https://docs.example.com/docs/intro",
        chunks=["local only query contract"],
    )

    _ = mocker.patch(
        "socket.create_connection", side_effect=AssertionError("query must stay local")
    )
    hits = _query_local(store, "local only query contract", limit=5)

    assert len(hits) == 1
    hit = hits[0]
    assert hit.source_id == source.source_id
    assert hit.snapshot_id == "snapshot-active"
    assert hit.document_id == "snapshot-active-doc-0"
    assert hit.chunk_index == 0
    assert hit.text == "local only query contract"


def test_query_local_searches_active_snapshots_only(
    connection: sqlite3.Connection,
    store: SQLiteStore,
    source: Source,
) -> None:
    _insert_snapshot_with_chunks(
        connection,
        store,
        source,
        "snapshot-stale",
        active=False,
        status=SnapshotStatus.STALE,
        document_locator="https://docs.example.com/docs/stale",
        chunks=["shared contract phrase from stale content"],
    )
    _insert_snapshot_with_chunks(
        connection,
        store,
        source,
        "snapshot-active",
        active=True,
        status=SnapshotStatus.INDEXED,
        document_locator="https://docs.example.com/docs/active",
        chunks=["shared contract phrase from active content"],
    )

    hits = _query_local(store, "shared contract phrase", limit=5)

    assert [hit.snapshot_id for hit in hits] == ["snapshot-active"]
    assert [hit.chunk_id for hit in hits] == ["snapshot-active-doc-0-chunk-0"]


def test_query_local_accepts_plain_text_and_respects_limit(
    connection: sqlite3.Connection,
    store: SQLiteStore,
    source: Source,
) -> None:
    _insert_snapshot_with_chunks(
        connection,
        store,
        source,
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

    hits = _query_local(store, "plain text query contract", limit=2)

    assert len(hits) == 2
    assert [hit.chunk_index for hit in hits] == [0, 1]
    assert [hit.text for hit in hits] == [
        "plain text query contract",
        "plain text query contract second chunk",
    ]


def test_query_local_returns_chunk_level_results_for_structured_content(
    connection: sqlite3.Connection,
    store: SQLiteStore,
    source: Source,
) -> None:
    _insert_snapshot_with_chunks(
        connection,
        store,
        source,
        "snapshot-active",
        active=True,
        status=SnapshotStatus.INDEXED,
        document_locator="https://docs.example.com/docs/guide",
        chunks=[
            "Guide > Intro Alpha paragraph",
            "Guide > Intro > Setup Beta paragraph",
        ],
    )

    hits = _query_local(store, "paragraph", limit=10)

    assert len(hits) == 2
    assert [hit.chunk_index for hit in hits] == [0, 1]
    assert "Guide > Intro" in hits[0].text
    assert "Guide > Intro > Setup" in hits[1].text


def test_query_local_passes_through_source_filter(
    connection: sqlite3.Connection,
    store: SQLiteStore,
    source: Source,
) -> None:
    _insert_snapshot_with_chunks(
        connection,
        store,
        source,
        "snapshot-active",
        active=True,
        status=SnapshotStatus.INDEXED,
        document_locator="https://docs.example.com/docs/guide",
        chunks=["shared filter term from source one"],
    )

    hits = _query_local(
        store,
        "shared filter term",
        limit=10,
        source_id=source.source_id,
    )

    assert len(hits) == 1
    assert hits[0].source_id == source.source_id


def test_query_local_json_returns_stable_envelope(
    connection: sqlite3.Connection,
    store: SQLiteStore,
    source: Source,
) -> None:
    _insert_snapshot_with_chunks(
        connection,
        store,
        source,
        "snapshot-active",
        active=True,
        status=SnapshotStatus.INDEXED,
        document_locator="https://docs.example.com/docs/guide",
        chunks=["shared machine query term"],
    )

    result = _query_local_json(store, "shared machine query term", limit=5)

    assert result.query_text == "shared machine query term"
    assert result.limit == 5
    assert result.source_id is None
    assert result.hit_count == 1


@pytest.mark.parametrize(
    ("query_text", "expected_locators"),
    [
        (
            "install api",
            [
                "https://github.com/code-yeongyu/oh-my-openagent/blob/main/README.md",
                "https://github.com/code-yeongyu/oh-my-openagent/tree/main/docs/guide.md",
                "https://github.com/code-yeongyu/oh-my-openagent/blob/main/examples/install-api.md",
                "https://github.com/code-yeongyu/oh-my-openagent/wiki",
            ],
        ),
        (
            "release notes",
            [
                "https://github.com/code-yeongyu/oh-my-openagent/releases",
                "https://github.com/code-yeongyu/oh-my-openagent/issues",
                "https://github.com/code-yeongyu/oh-my-openagent/pulls",
                "https://github.com/code-yeongyu/oh-my-openagent/compare/main...HEAD",
            ],
        ),
    ],
)
def test_query_local_orders_github_repo_intents_exactly(
    connection: sqlite3.Connection,
    store: SQLiteStore,
    source: Source,
    query_text: str,
    expected_locators: list[str],
) -> None:
    _seed_github_repo_snapshot(connection, store, source)

    result = _query_local_json(store, query_text, limit=5)

    assert [hit.document_locator for hit in result.hits] == expected_locators


def test_query_local_boosts_guidance_before_releases_for_repo_operational_intent(
    connection: sqlite3.Connection,
    store: SQLiteStore,
    source: Source,
) -> None:
    _seed_github_repo_snapshot(connection, store, source)

    result = _query_local_json(store, "agent command", limit=5)

    assert [hit.document_locator for hit in result.hits] == [
        "https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
        "https://github.com/code-yeongyu/oh-my-openagent/releases",
    ]


def test_query_local_treats_instructions_as_repo_operational_intent(
    connection: sqlite3.Connection,
    store: SQLiteStore,
    source: Source,
) -> None:
    _seed_github_repo_snapshot(connection, store, source)

    result = _query_local_json(store, "instructions", limit=5)

    assert [hit.document_locator for hit in result.hits] == [
        "https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
        "https://github.com/code-yeongyu/oh-my-openagent/blob/main/CLAUDE.md",
        "https://github.com/code-yeongyu/oh-my-openagent/blob/main/llms.txt",
        "https://github.com/code-yeongyu/oh-my-openagent/releases",
    ]


def test_query_local_treats_how_to_work_phrase_as_repo_operational_intent(
    connection: sqlite3.Connection,
    store: SQLiteStore,
    source: Source,
) -> None:
    _seed_github_repo_snapshot(connection, store, source)

    result = _query_local_json(store, "how to work in this repo", limit=5)

    assert [hit.document_locator for hit in result.hits] == [
        "https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
        "https://github.com/code-yeongyu/oh-my-openagent/blob/main/CLAUDE.md",
        "https://github.com/code-yeongyu/oh-my-openagent/blob/main/llms.txt",
        "https://github.com/code-yeongyu/oh-my-openagent/releases",
    ]


def test_query_local_does_not_treat_repo_file_named_issues_as_management(
    connection: sqlite3.Connection,
    store: SQLiteStore,
    source: Source,
) -> None:
    snapshot = Snapshot(
        snapshot_id="snapshot-github-issues-file",
        source_id=source.source_id,
        status=SnapshotStatus.INDEXED,
        content_hash="hash-snapshot-github-issues-file",
        is_active=True,
    )
    store.insert_snapshot(snapshot)
    stored_documents = store.replace_snapshot_documents(
        snapshot.snapshot_id,
        source.source_id,
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
                snapshot.snapshot_id,
                document.document_id,
                0,
                text,
                "{}",
            ),
        )
        row = cast(
            tuple[int] | None,
            connection.execute(
                "SELECT rowid FROM chunks WHERE chunk_id = ?", (chunk_id,)
            ).fetchone(),
        )
        if row is None:
            raise AssertionError("expected chunk rowid")
        _ = connection.execute(
            "INSERT INTO chunk_fts(rowid, chunk_id, text) VALUES (?, ?, ?)",
            (row[0], chunk_id, text),
        )
    connection.commit()
    store.activate_snapshot(source.source_id, snapshot.snapshot_id)

    result = _query_local_json(store, "release notes", limit=5)

    assert [hit.document_locator for hit in result.hits] == [
        "https://github.com/code-yeongyu/oh-my-openagent/releases",
        "https://github.com/code-yeongyu/oh-my-openagent/blob/main/issues.md",
    ]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))

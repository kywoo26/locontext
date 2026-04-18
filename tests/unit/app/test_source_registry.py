from locontext.app.sources import list_sources, register_source, remove_source
from locontext.domain.models import (
    Chunk,
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


def test_register_source_creates_web_source(store: SQLiteStore) -> None:
    result = register_source(
        store,
        "https://docs.example.com/docs/getting-started?utm_source=test#intro",
    )
    assert result.created
    assert (
        result.source.canonical_locator
        == "https://docs.example.com/docs/getting-started"
    )
    assert result.source.docset_root == "https://docs.example.com"


def test_register_source_persists_narrowed_docset_root_for_new_github_repo(
    store: SQLiteStore,
) -> None:
    result = register_source(
        store,
        "https://github.com/org/repo/blob/main/README.md?utm_source=test",
    )
    assert result.created
    assert (
        result.source.canonical_locator
        == "https://github.com/org/repo/blob/main/README.md"
    )
    assert result.source.docset_root == "https://github.com/org/repo"
    stored = store.get_source(result.source.source_id)
    assert stored is not None
    assert stored.docset_root == "https://github.com/org/repo"


def test_register_source_persists_narrowed_docset_root_for_new_article_leaf(
    store: SQLiteStore,
) -> None:
    result = register_source(
        store, "https://example.com/blog/post-slug?utm_source=test#intro"
    )
    assert result.created
    assert result.source.canonical_locator == "https://example.com/blog/post-slug"
    assert result.source.docset_root == "https://example.com/blog/post-slug"
    stored = store.get_source(result.source.source_id)
    assert stored is not None
    assert stored.docset_root == "https://example.com/blog/post-slug"


def test_register_source_dedupes_equivalent_urls(store: SQLiteStore) -> None:
    first = register_source(
        store,
        "https://docs.example.com/docs/getting-started?utm_source=test#intro",
    )
    second = register_source(store, "https://docs.example.com/docs/getting-started")
    assert first.created
    assert not second.created
    assert first.source.source_id == second.source.source_id


def test_list_sources_is_deterministic(store: SQLiteStore) -> None:
    _ = register_source(store, "https://docs.example.com/docs/beta")
    _ = register_source(store, "https://docs.example.com/docs/alpha")
    sources = list_sources(store)
    assert [source.canonical_locator for source in sources] == [
        "https://docs.example.com/docs/alpha",
        "https://docs.example.com/docs/beta",
    ]


def test_remove_source_deletes_related_local_state(store: SQLiteStore) -> None:
    source = Source(
        source_id="source-1",
        source_kind=SourceKind.WEB,
        requested_locator="https://docs.example.com/docs",
        resolved_locator="https://docs.example.com/docs",
        canonical_locator="https://docs.example.com/docs",
        docset_root="https://docs.example.com/docs",
    )
    store.upsert_source(source)
    snapshot = Snapshot(
        snapshot_id="snapshot-1",
        source_id=source.source_id,
        status=SnapshotStatus.INDEXED,
        is_active=True,
    )
    store.insert_snapshot(snapshot)
    stored_documents = store.replace_snapshot_documents(
        snapshot.snapshot_id,
        source.source_id,
        [
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs/page",
                resolved_locator="https://docs.example.com/docs/page",
                canonical_locator="https://docs.example.com/docs/page",
                title="Page",
                content_hash="hash-1",
            )
        ],
    )
    store.replace_snapshot_chunks(
        snapshot.snapshot_id,
        [
            Chunk(
                chunk_id="chunk-1",
                source_id=source.source_id,
                snapshot_id=snapshot.snapshot_id,
                document_id=stored_documents[0].document_id,
                chunk_index=0,
                text="hello world",
            )
        ],
    )
    store.activate_snapshot(source.source_id, snapshot.snapshot_id)
    result = remove_source(store, source.source_id)
    assert result.removed
    assert store.get_source(source.source_id) is None
    assert store.get_active_snapshot(source.source_id) is None
    assert store.list_documents(snapshot.snapshot_id) == []
    assert store.search_chunks("hello", limit=10) == []


def test_remove_source_is_idempotent_for_missing_source(store: SQLiteStore) -> None:
    first = remove_source(store, "missing-source")
    second = remove_source(store, "missing-source")
    assert not first.removed
    assert not second.removed
    assert first.source_id == "missing-source"
    assert second.source_id == "missing-source"

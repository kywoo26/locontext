from locontext.app.sources import get_source_status, list_source_status
from locontext.domain.models import (
    Chunk,
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


def _add_source(store: SQLiteStore, source_id: str, locator: str) -> Source:
    source = Source(
        source_id=source_id,
        source_kind=SourceKind.WEB,
        requested_locator=locator,
        resolved_locator=locator,
        canonical_locator=locator,
        docset_root=locator,
    )
    store.upsert_source(source)
    return source


def test_list_source_status_is_stable_for_unrefreshed_sources(
    store: SQLiteStore,
) -> None:
    _ = _add_source(store, "source-b", "https://docs.example.com/docs/b")
    _ = _add_source(store, "source-a", "https://docs.example.com/docs/a")
    statuses = list_source_status(store)
    assert [status.source_id for status in statuses] == ["source-a", "source-b"]
    assert [status.document_count for status in statuses] == [0, 0]
    assert [status.chunk_count for status in statuses] == [0, 0]
    assert [status.active_snapshot_id for status in statuses] == [None, None]
    assert [status.snapshot_status for status in statuses] == [None, None]
    assert [status.fetched_at for status in statuses] == [None, None]
    assert [status.freshness_state for status in statuses] == [
        "never-refreshed",
        "never-refreshed",
    ]


def test_list_source_status_keeps_never_refreshed_and_unhealthy_empty_distinct(
    store: SQLiteStore,
) -> None:
    never_refreshed = _add_source(store, "source-b", "https://docs.example.com/docs/b")
    active_zero_document = _add_source(
        store, "source-a", "https://docs.example.com/docs/a"
    )
    snapshot = Snapshot(
        snapshot_id="snapshot-0",
        source_id=active_zero_document.source_id,
        status=SnapshotStatus.INDEXED,
        fetched_at="2026-04-12T00:00:00+00:00",
        is_active=True,
    )
    store.insert_snapshot(snapshot)
    _ = store.replace_snapshot_documents(
        snapshot.snapshot_id, active_zero_document.source_id, []
    )
    store.activate_snapshot(active_zero_document.source_id, snapshot.snapshot_id)
    statuses = list_source_status(store)
    assert [status.source_id for status in statuses] == [
        active_zero_document.source_id,
        never_refreshed.source_id,
    ]
    assert [status.document_count for status in statuses] == [0, 0]
    assert [status.chunk_count for status in statuses] == [0, 0]
    assert [status.active_snapshot_id for status in statuses] == [
        snapshot.snapshot_id,
        None,
    ]
    assert [status.freshness_state for status in statuses] == [
        "unhealthy-empty",
        "never-refreshed",
    ]
    assert [status.freshness_reason for status in statuses] == [
        "zero documents in active snapshot",
        "source has never been refreshed",
    ]


def test_get_source_status_reports_active_snapshot_counts(store: SQLiteStore) -> None:
    source = _add_source(store, "source-1", "https://docs.example.com/docs")
    snapshot = Snapshot(
        snapshot_id="snapshot-1",
        source_id=source.source_id,
        status=SnapshotStatus.INDEXED,
        fetched_at="2026-04-12T00:00:00+00:00",
        is_active=True,
    )
    store.insert_snapshot(snapshot)
    documents = store.replace_snapshot_documents(
        snapshot.snapshot_id,
        source.source_id,
        [
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs/guide",
                resolved_locator="https://docs.example.com/docs/guide",
                canonical_locator="https://docs.example.com/docs/guide",
                title="Guide",
                content_hash="doc-hash-1",
            )
        ],
    )
    store.replace_snapshot_chunks(
        snapshot.snapshot_id,
        [
            Chunk(
                chunk_id=f"{documents[0].document_id}-chunk-0",
                source_id=source.source_id,
                snapshot_id=snapshot.snapshot_id,
                document_id=documents[0].document_id,
                chunk_index=0,
                text="hello world",
            )
        ],
    )
    status = get_source_status(store, source.source_id)
    assert status is not None
    if status is None:
        raise AssertionError("expected source status")
    assert status.source_id == source.source_id
    assert status.active_snapshot_id == snapshot.snapshot_id
    assert status.snapshot_status == SnapshotStatus.INDEXED
    assert status.document_count == 1
    assert status.chunk_count == 1
    assert status.fetched_at == "2026-04-12T00:00:00+00:00"
    assert status.freshness_state == "current"


def test_get_source_status_reports_unhealthy_empty_for_active_zero_documents(
    store: SQLiteStore,
) -> None:
    source = _add_source(store, "source-2", "https://docs.example.com/docs")
    snapshot = Snapshot(
        snapshot_id="snapshot-2",
        source_id=source.source_id,
        status=SnapshotStatus.INDEXED,
        fetched_at="2026-04-12T00:00:00+00:00",
        is_active=True,
    )
    store.insert_snapshot(snapshot)
    _ = store.replace_snapshot_documents(snapshot.snapshot_id, source.source_id, [])
    status = get_source_status(store, source.source_id)
    assert status is not None
    if status is None:
        raise AssertionError("expected source status")
    assert status.document_count == 0
    assert status.chunk_count == 0
    assert status.freshness_state == "unhealthy-empty"
    assert status.freshness_reason == "zero documents in active snapshot"


def test_get_source_status_keeps_stale_advisory_for_non_empty_stale_snapshot(
    store: SQLiteStore,
) -> None:
    source = _add_source(store, "source-3", "https://docs.example.com/docs")
    snapshot = Snapshot(
        snapshot_id="snapshot-3",
        source_id=source.source_id,
        status=SnapshotStatus.STALE,
        fetched_at="2026-04-12T00:00:00+00:00",
        is_active=True,
    )
    store.insert_snapshot(snapshot)
    documents = store.replace_snapshot_documents(
        snapshot.snapshot_id,
        source.source_id,
        [
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs/guide",
                resolved_locator="https://docs.example.com/docs/guide",
                canonical_locator="https://docs.example.com/docs/guide",
                title="Guide",
                content_hash="doc-hash-1",
            )
        ],
    )
    store.replace_snapshot_chunks(
        snapshot.snapshot_id,
        [
            Chunk(
                chunk_id=f"{documents[0].document_id}-chunk-0",
                source_id=source.source_id,
                snapshot_id=snapshot.snapshot_id,
                document_id=documents[0].document_id,
                chunk_index=0,
                text="hello world",
            )
        ],
    )
    status = get_source_status(store, source.source_id)
    assert status is not None
    if status is None:
        raise AssertionError("expected source status")
    assert status.document_count == 1
    assert status.chunk_count == 1
    assert status.freshness_state == "stale-advisory"
    assert (
        status.freshness_reason == "active snapshot is stale until manually refreshed"
    )


def test_get_source_status_returns_none_for_missing_source(store: SQLiteStore) -> None:
    assert get_source_status(store, "missing-source") is None

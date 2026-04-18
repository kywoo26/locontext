import pytest

from locontext.app.refresh import get_freshness_state
from locontext.domain.models import (
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


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


def _activate_snapshot(
    store: SQLiteStore,
    source: Source,
    *,
    snapshot_id: str,
    status: SnapshotStatus,
    documents: list[DiscoveredDocument] | None = None,
) -> Snapshot:
    snapshot = Snapshot(
        snapshot_id=snapshot_id,
        source_id=source.source_id,
        status=status,
        fetched_at="2026-04-12T00:00:00+00:00",
        is_active=True,
    )
    store.insert_snapshot(snapshot)
    if documents is not None:
        _ = store.replace_snapshot_documents(
            snapshot.snapshot_id, source.source_id, documents
        )
    store.activate_snapshot(source.source_id, snapshot.snapshot_id)
    if status is SnapshotStatus.STALE:
        store.mark_snapshot_stale(snapshot.snapshot_id)
    return snapshot


def test_never_refreshed_source_reports_never_refreshed(
    store: SQLiteStore, source: Source
) -> None:
    state = get_freshness_state(store, source.source_id)
    assert state.code == "never-refreshed"
    assert state.reason == "source has never been refreshed"


def test_active_snapshot_with_zero_documents_is_unhealthy_empty(
    store: SQLiteStore, source: Source
) -> None:
    _ = _activate_snapshot(
        store,
        source,
        snapshot_id="snapshot-1",
        status=SnapshotStatus.INDEXED,
        documents=[],
    )
    state = get_freshness_state(store, source.source_id)
    assert state.code == "unhealthy-empty"
    assert state.reason == "zero documents in active snapshot"


def test_active_stale_snapshot_with_zero_documents_is_unhealthy_empty(
    store: SQLiteStore, source: Source
) -> None:
    _ = _activate_snapshot(
        store,
        source,
        snapshot_id="snapshot-1",
        status=SnapshotStatus.STALE,
        documents=[],
    )
    state = get_freshness_state(store, source.source_id)
    assert state.code == "unhealthy-empty"
    assert state.reason == "zero documents in active snapshot"


def test_active_snapshot_with_documents_is_current(
    store: SQLiteStore, source: Source
) -> None:
    _ = _activate_snapshot(
        store,
        source,
        snapshot_id="snapshot-1",
        status=SnapshotStatus.INDEXED,
        documents=[
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs/guide",
                resolved_locator="https://docs.example.com/docs/guide",
                canonical_locator="https://docs.example.com/docs/guide",
                title="Guide",
                content_hash="doc-hash-1",
            )
        ],
    )
    state = get_freshness_state(store, source.source_id)
    assert state.code == "current"
    assert state.reason == "active snapshot is current"


def test_active_stale_snapshot_with_documents_is_advisory_only(
    store: SQLiteStore, source: Source
) -> None:
    _ = _activate_snapshot(
        store,
        source,
        snapshot_id="snapshot-1",
        status=SnapshotStatus.STALE,
        documents=[
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs/guide",
                resolved_locator="https://docs.example.com/docs/guide",
                canonical_locator="https://docs.example.com/docs/guide",
                title="Guide",
                content_hash="doc-hash-1",
            )
        ],
    )
    state = get_freshness_state(store, source.source_id)
    assert state.code == "stale-advisory"
    assert state.reason == "active snapshot is stale until manually refreshed"

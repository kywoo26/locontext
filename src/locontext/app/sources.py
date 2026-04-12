from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from ..domain.models import SnapshotStatus, Source, SourceKind
from ..sources.web.canonicalize import canonicalize_locator, infer_docset_root
from ..store.sqlite import SQLiteStore
from .refresh import get_freshness_state


@dataclass(slots=True)
class SourceRegistrationResult:
    source: Source
    created: bool


@dataclass(slots=True)
class SourceRemovalResult:
    source_id: str
    removed: bool


@dataclass(slots=True)
class SourceStatusResult:
    source_id: str
    canonical_locator: str
    docset_root: str
    active_snapshot_id: str | None
    snapshot_status: SnapshotStatus | None
    document_count: int
    chunk_count: int
    fetched_at: str | None
    etag: str | None
    last_modified: str | None
    freshness_state: str
    freshness_reason: str


def register_source(
    store: SQLiteStore, requested_locator: str
) -> SourceRegistrationResult:
    canonicalized = canonicalize_locator(requested_locator)
    existing = store.get_source_by_canonical_locator(canonicalized.canonical_locator)
    if existing is not None:
        return SourceRegistrationResult(source=existing, created=False)

    now = datetime.now(UTC).isoformat()
    source = Source(
        source_id=uuid4().hex,
        source_kind=SourceKind.WEB,
        requested_locator=canonicalized.requested_locator,
        resolved_locator=canonicalized.resolved_locator,
        canonical_locator=canonicalized.canonical_locator,
        docset_root=infer_docset_root(canonicalized.canonical_locator),
        created_at=now,
        updated_at=now,
    )
    store.upsert_source(source)
    return SourceRegistrationResult(source=source, created=True)


def list_sources(store: SQLiteStore) -> list[Source]:
    return store.list_sources()


def remove_source(store: SQLiteStore, source_id: str) -> SourceRemovalResult:
    removed = store.delete_source(source_id)
    return SourceRemovalResult(source_id=source_id, removed=removed)


def list_source_status(store: SQLiteStore) -> list[SourceStatusResult]:
    return [
        _source_status_from_source(store, source) for source in store.list_sources()
    ]


def get_source_status(store: SQLiteStore, source_id: str) -> SourceStatusResult | None:
    source = store.get_source(source_id)
    if source is None:
        return None
    return _source_status_from_source(store, source)


def _source_status_from_source(
    store: SQLiteStore, source: Source
) -> SourceStatusResult:
    active_snapshot = store.get_active_snapshot(source.source_id)
    if active_snapshot is None:
        return SourceStatusResult(
            source_id=source.source_id,
            canonical_locator=source.canonical_locator,
            docset_root=source.docset_root,
            active_snapshot_id=None,
            snapshot_status=None,
            document_count=0,
            chunk_count=0,
            fetched_at=None,
            etag=None,
            last_modified=None,
            freshness_state="never-refreshed",
            freshness_reason="source has never been refreshed",
        )
    freshness = get_freshness_state(store, source.source_id)
    return SourceStatusResult(
        source_id=source.source_id,
        canonical_locator=source.canonical_locator,
        docset_root=source.docset_root,
        active_snapshot_id=active_snapshot.snapshot_id,
        snapshot_status=active_snapshot.status,
        document_count=store.count_documents(active_snapshot.snapshot_id),
        chunk_count=store.count_chunks(active_snapshot.snapshot_id),
        fetched_at=active_snapshot.fetched_at,
        etag=active_snapshot.etag,
        last_modified=active_snapshot.last_modified,
        freshness_state=freshness.code,
        freshness_reason=freshness.reason,
    )

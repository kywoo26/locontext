from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from ..domain.models import (
    SnapshotStatus,
    Source,
    SourceKind,
    SourceSet,
)
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


@dataclass(slots=True)
class ProjectStatusResult:
    source_count: int
    source_set_count: int
    active_snapshot_count: int
    document_count: int
    chunk_count: int


@dataclass(slots=True)
class SourceSetMemberResult:
    source_id: str
    canonical_locator: str
    member_index: int


@dataclass(slots=True)
class SourceSetResult:
    source_set_id: str
    set_name: str
    members: tuple[SourceSetMemberResult, ...] = ()


@dataclass(slots=True)
class SourceSetCreationResult:
    source_set: SourceSetResult
    created: bool
    duplicate_source_ids: tuple[str, ...] = ()


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


def get_project_status(store: SQLiteStore) -> ProjectStatusResult:
    return ProjectStatusResult(
        source_count=store.count_sources(),
        source_set_count=store.count_source_sets(),
        active_snapshot_count=store.count_active_snapshots(),
        document_count=store.count_all_documents(),
        chunk_count=store.count_all_chunks(),
    )


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


def create_source_set(
    store: SQLiteStore, set_name: str, source_ids: list[str]
) -> SourceSetCreationResult:
    normalized_source_ids, duplicate_source_ids = _normalize_source_ids(source_ids)
    missing_source_ids = tuple(
        source_id
        for source_id in normalized_source_ids
        if store.get_source(source_id) is None
    )
    if missing_source_ids:
        missing = ", ".join(missing_source_ids)
        raise KeyError(f"Sources not found for source set {set_name!r}: {missing}")

    existing = store.get_source_set(set_name)
    source_set_id = existing.source_set_id if existing is not None else uuid4().hex
    _ = store.create_source_set(source_set_id, set_name, list(normalized_source_ids))
    source_set = store.get_source_set(set_name)
    if source_set is None:
        raise RuntimeError(f"Source set could not be loaded after save: {set_name}")
    return SourceSetCreationResult(
        source_set=_source_set_result_from_store(source_set),
        created=existing is None,
        duplicate_source_ids=duplicate_source_ids,
    )


def list_source_sets(store: SQLiteStore) -> list[SourceSetResult]:
    return [
        _source_set_result_from_store(source_set)
        for source_set in store.list_source_sets()
    ]


def get_source_set(store: SQLiteStore, set_name: str) -> SourceSetResult | None:
    source_set = store.get_source_set(set_name)
    if source_set is None:
        return None
    return _source_set_result_from_store(source_set)


def _source_set_result_from_store(source_set: SourceSet) -> SourceSetResult:
    return SourceSetResult(
        source_set_id=source_set.source_set_id,
        set_name=source_set.set_name,
        members=tuple(
            SourceSetMemberResult(
                source_id=member.source_id,
                canonical_locator=member.canonical_locator,
                member_index=member.member_index,
            )
            for member in source_set.members
        ),
    )


def _normalize_source_ids(
    source_ids: list[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    normalized_source_ids: list[str] = []
    duplicate_source_ids: list[str] = []
    seen: set[str] = set()

    for source_id in source_ids:
        if source_id in seen:
            duplicate_source_ids.append(source_id)
            continue
        seen.add(source_id)
        normalized_source_ids.append(source_id)

    return tuple(normalized_source_ids), tuple(duplicate_source_ids)

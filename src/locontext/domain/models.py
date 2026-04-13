from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SourceKind(StrEnum):
    WEB = "web"


class SnapshotStatus(StrEnum):
    PENDING = "pending"
    INDEXED = "indexed"
    STALE = "stale"
    FAILED = "failed"


@dataclass(slots=True)
class Source:
    source_id: str
    source_kind: SourceKind
    requested_locator: str
    resolved_locator: str | None
    canonical_locator: str
    docset_root: str
    active_snapshot_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(slots=True)
class SourceSetMember:
    source_id: str
    canonical_locator: str
    member_index: int


@dataclass(slots=True)
class SourceSet:
    source_set_id: str
    set_name: str
    members: tuple[SourceSetMember, ...] = ()


@dataclass(slots=True)
class Snapshot:
    snapshot_id: str
    source_id: str
    status: SnapshotStatus
    fetched_at: str | None = None
    content_hash: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    is_active: bool = False


@dataclass(slots=True)
class Document:
    document_id: str
    source_id: str
    snapshot_id: str
    requested_locator: str
    resolved_locator: str
    canonical_locator: str
    title: str | None = None
    section_path: tuple[str, ...] = ()
    content_hash: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveredDocument:
    requested_locator: str
    resolved_locator: str
    canonical_locator: str
    title: str | None = None
    content_hash: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveryWarning:
    locator: str
    reason: str


@dataclass(slots=True)
class DiscoveryOutcome:
    documents: list[DiscoveredDocument] = field(default_factory=list)
    warning_count: int = 0
    warning_samples: list[DiscoveryWarning] = field(default_factory=list)


@dataclass(slots=True)
class Chunk:
    chunk_id: str
    source_id: str
    snapshot_id: str
    document_id: str
    chunk_index: int
    text: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class QueryHit:
    source_id: str
    snapshot_id: str
    document_id: str
    chunk_id: str
    chunk_index: int
    text: str
    score: float
    metadata: dict[str, object] = field(default_factory=dict)

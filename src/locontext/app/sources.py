from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from ..domain.models import Source, SourceKind
from ..sources.web.canonicalize import canonicalize_locator, infer_docset_root
from ..store.sqlite import SQLiteStore


@dataclass(slots=True)
class SourceRegistrationResult:
    source: Source
    created: bool


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

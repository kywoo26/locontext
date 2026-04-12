from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module
from typing import Final, Protocol, cast
from uuid import uuid4

from ..domain.contracts import DiscoveryProvider, IndexingEngine
from ..domain.models import DiscoveredDocument, Snapshot, SnapshotStatus, Source
from ..sources.web.discovery import filter_and_order_discovered_documents
from ..store.sqlite import SQLiteStore


@dataclass(slots=True)
class RefreshResult:
    source_id: str
    snapshot_id: str | None
    changed: bool
    document_count: int


class RefreshOrchestrator:
    _store: Final[SQLiteStore]
    _discovery_provider: Final[DiscoveryProvider]
    _indexing_engine: Final[IndexingEngine]

    def __init__(
        self,
        store: SQLiteStore,
        discovery_provider: DiscoveryProvider | None = None,
        indexing_engine: IndexingEngine | None = None,
    ) -> None:
        self._store = store
        self._discovery_provider = discovery_provider or _default_discovery_provider()
        self._indexing_engine = indexing_engine or _default_indexing_engine(store)

    def refresh_source(self, source_id: str) -> RefreshResult:
        source = self._require_source(source_id)
        discovered = list(self._discovery_provider.discover(source))
        ordered = filter_and_order_discovered_documents(source, discovered)
        manifest_hash = _manifest_hash(ordered)

        active_snapshot = self._store.get_active_snapshot(source_id)
        if (
            active_snapshot is not None
            and active_snapshot.content_hash == manifest_hash
        ):
            documents = self._store.list_documents(active_snapshot.snapshot_id)
            return RefreshResult(
                source_id=source_id,
                snapshot_id=active_snapshot.snapshot_id,
                changed=False,
                document_count=len(documents),
            )

        snapshot = Snapshot(
            snapshot_id=uuid4().hex,
            source_id=source_id,
            status=SnapshotStatus.PENDING,
            content_hash=manifest_hash,
            is_active=False,
        )
        self._store.insert_snapshot(snapshot)
        documents = self._store.replace_snapshot_documents(
            snapshot.snapshot_id, source_id, ordered
        )

        try:
            self._indexing_engine.reindex_snapshot(source, snapshot, documents)
            self._store.activate_snapshot(source_id, snapshot.snapshot_id)
        except Exception:
            self._store.mark_snapshot_failed(snapshot.snapshot_id)
            raise

        return RefreshResult(
            source_id=source_id,
            snapshot_id=snapshot.snapshot_id,
            changed=True,
            document_count=len(documents),
        )

    def reindex_source(self, source_id: str) -> RefreshResult:
        source = self._require_source(source_id)
        snapshot = self._store.get_active_snapshot(source_id)
        if snapshot is None:
            raise KeyError(f"Active snapshot not found for source: {source_id}")

        documents = self._store.list_documents(snapshot.snapshot_id)
        self._indexing_engine.reindex_snapshot(source, snapshot, documents)
        return RefreshResult(
            source_id=source_id,
            snapshot_id=snapshot.snapshot_id,
            changed=False,
            document_count=len(documents),
        )

    def remove_source(self, source_id: str) -> None:
        self._indexing_engine.remove_source(source_id)
        self._store.delete_source(source_id)

    def _require_source(self, source_id: str) -> Source:
        source = self._store.get_source(source_id)
        if source is None:
            raise KeyError(f"Source not found: {source_id}")
        return source


def _manifest_hash(documents: list[DiscoveredDocument]) -> str:
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


class _WebProviderModule(Protocol):
    WebDiscoveryProvider: type[DiscoveryProvider]


class _IndexingEngineFactory(Protocol):
    def __call__(self, connection: sqlite3.Connection) -> IndexingEngine: ...


class _EngineModule(Protocol):
    SQLiteLexicalEngine: _IndexingEngineFactory


def _default_discovery_provider() -> DiscoveryProvider:
    module = cast(
        _WebProviderModule,
        cast(object, import_module("locontext.sources.web.provider")),
    )
    return module.WebDiscoveryProvider()


def _default_indexing_engine(store: SQLiteStore) -> IndexingEngine:
    module = cast(
        _EngineModule,
        cast(object, import_module("locontext.engine.sqlite_lexical")),
    )
    return module.SQLiteLexicalEngine(store.connection)

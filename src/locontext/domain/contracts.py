from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .models import DiscoveredDocument, Document, QueryHit, Snapshot, Source


class DiscoveryProvider(Protocol):
    def discover(self, source: Source) -> Sequence[DiscoveredDocument]:
        """Return discovered documents for a source."""
        ...


class IndexingEngine(Protocol):
    def reindex_snapshot(
        self,
        source: Source,
        snapshot: Snapshot,
        documents: Sequence[Document],
    ) -> None:
        """Reindex the local snapshot content."""
        ...

    def remove_source(self, source_id: str) -> None:
        """Delete indexed content for a source."""
        ...


class QueryEngine(Protocol):
    def query(self, text: str, *, limit: int) -> Sequence[QueryHit]:
        """Search locally indexed snapshot content."""
        ...

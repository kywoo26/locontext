from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from .models import DiscoveryOutcome, Document, QueryHit, Snapshot, Source


class DiscoveryProvider(Protocol):
    def discover(self, source: Source) -> DiscoveryOutcome:
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


@dataclass(frozen=True, slots=True)
class QueryEngineDescriptor:
    engine_kind: Literal["lexical", "semantic", "hybrid"]
    engine_name: str
    semantic_ready: bool
    is_baseline: bool


class QueryEngine(Protocol):
    def query(
        self,
        text: str,
        *,
        limit: int,
        source_id: str | None = None,
    ) -> list[QueryHit]:
        """Return local query hits for the active snapshot set."""
        ...

    def describe(self) -> QueryEngineDescriptor:
        """Return engine capability and readiness metadata."""
        ...

from __future__ import annotations

from collections.abc import Sequence

from ..domain.models import Document, Snapshot, Source


class NoopIndexingEngine:
    def reindex_snapshot(
        self,
        _source: Source,
        _snapshot: Snapshot,
        _documents: Sequence[Document],
    ) -> None:
        return None

    def remove_source(self, _source_id: str) -> None:
        return None

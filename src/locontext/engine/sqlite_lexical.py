from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence

from ..domain.models import Chunk, Document, QueryHit, Snapshot, Source
from ..store.sqlite import SQLiteStore

_QUERY_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z_]+")
_TEXT_METADATA_KEY = "extracted_text"


class SQLiteLexicalEngine:
    _store: SQLiteStore

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._store = SQLiteStore(connection)

    def reindex_snapshot(
        self,
        source: Source,
        snapshot: Snapshot,
        documents: Sequence[Document],
    ) -> None:
        chunks: list[Chunk] = []
        for document in documents:
            text = _document_text(document)
            if not text:
                continue
            chunks.append(
                Chunk(
                    chunk_id=f"{document.document_id}-chunk-0",
                    source_id=source.source_id,
                    snapshot_id=snapshot.snapshot_id,
                    document_id=document.document_id,
                    chunk_index=0,
                    text=text,
                    metadata={},
                )
            )
        self._store.replace_snapshot_chunks(snapshot.snapshot_id, chunks)

    def query(self, text: str, *, limit: int) -> list[QueryHit]:
        if limit <= 0:
            return []
        match_query = _plain_text_match_query(text)
        if match_query is None:
            return []
        return self._store.search_chunks(match_query, limit=limit)

    def remove_source(self, source_id: str) -> None:
        self._store.delete_source(source_id)


def _document_text(document: Document) -> str:
    value = document.metadata.get(_TEXT_METADATA_KEY)
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def _plain_text_match_query(text: str) -> str | None:
    terms: list[str] = _QUERY_TOKEN_PATTERN.findall(text)
    if not terms:
        return None
    return " AND ".join(f'"{term}"' for term in terms)

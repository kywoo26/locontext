from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence
from typing import cast

from ..domain.models import Chunk, Document, QueryHit, Snapshot, Source
from ..store.sqlite import SQLiteStore

_QUERY_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z_]+")
_TEXT_METADATA_KEY = "extracted_text"
_STRUCTURED_CONTENT_KEY = "structured_content"


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
            chunks.extend(
                build_document_chunks(
                    document=document,
                    source_id=source.source_id,
                    snapshot_id=snapshot.snapshot_id,
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
        _ = self._store.delete_source(source_id)


def _document_text(document: Document) -> str:
    value = document.metadata.get(_TEXT_METADATA_KEY)
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def build_document_chunks(
    *,
    document: Document,
    source_id: str,
    snapshot_id: str,
) -> list[Chunk]:
    structured_blocks = _structured_blocks(document)
    if structured_blocks:
        return build_chunks_from_structure(
            title=document.title,
            blocks=structured_blocks,
            chunk_prefix=document.document_id,
            source_id=source_id,
            snapshot_id=snapshot_id,
            document_id=document.document_id,
        )

    text = _document_text(document)
    if not text:
        return []
    return [
        Chunk(
            chunk_id=f"{document.document_id}-chunk-0",
            source_id=source_id,
            snapshot_id=snapshot_id,
            document_id=document.document_id,
            chunk_index=0,
            text=text,
            metadata={},
        )
    ]


def build_chunks_from_structure(
    *,
    title: str | None,
    blocks: Sequence[dict[str, object]],
    chunk_prefix: str,
    source_id: str = "source",
    snapshot_id: str = "snapshot",
    document_id: str = "document",
) -> list[Chunk]:
    heading_stack: list[str] = [title] if title else []
    chunk_groups: list[tuple[tuple[str, ...], list[str]]] = []
    current_section: tuple[str, ...] = tuple(heading_stack)
    current_lines: list[str] = []

    def flush() -> None:
        if current_lines:
            chunk_groups.append((current_section, current_lines.copy()))
            current_lines.clear()

    for block in blocks:
        kind = cast(str, block.get("kind", ""))
        text = cast(str, block.get("text", "")).strip()
        if not text:
            continue
        if kind == "heading":
            flush()
            level = cast(int, block.get("level", 1))
            base_title = [title] if title else []
            relative_headings = heading_stack[len(base_title) :]
            relative_headings = relative_headings[: max(level - 1, 0)]
            heading_stack = base_title + relative_headings + [text]
            current_section = tuple(heading_stack)
            continue
        if kind in {"paragraph", "list_item"}:
            current_lines.append(text)
            continue
        current_lines.append(text)

    flush()

    chunks: list[Chunk] = []
    for chunk_index, (section_path, lines) in enumerate(chunk_groups):
        prefix = " > ".join(section_path)
        chunk_text = "\n".join(lines)
        if prefix:
            chunk_text = f"{prefix}\n{chunk_text}"
        chunks.append(
            Chunk(
                chunk_id=f"{chunk_prefix}-chunk-{chunk_index}",
                source_id=source_id,
                snapshot_id=snapshot_id,
                document_id=document_id,
                chunk_index=chunk_index,
                text=chunk_text,
                metadata={"section_path": list(section_path)},
            )
        )
    return chunks


def _structured_blocks(document: Document) -> tuple[dict[str, object], ...]:
    value = document.metadata.get(_STRUCTURED_CONTENT_KEY)
    if not isinstance(value, list):
        return ()
    blocks: list[dict[str, object]] = []
    for item in cast(list[object], value):
        if not isinstance(item, dict):
            return ()
        blocks.append(cast(dict[str, object], item))
    return tuple(blocks)


def _plain_text_match_query(text: str) -> str | None:
    terms: list[str] = _QUERY_TOKEN_PATTERN.findall(text)
    if not terms:
        return None
    return " AND ".join(f'"{term}"' for term in terms)

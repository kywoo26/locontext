from __future__ import annotations

import json
import sqlite3
from typing import Final, cast

from ..domain.models import (
    Chunk,
    DiscoveredDocument,
    Document,
    QueryHit,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from .migrations import apply_migrations


class SQLiteStore:
    _connection: Final[sqlite3.Connection]

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def ensure_schema(self) -> None:
        apply_migrations(self._connection)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def upsert_source(self, source: Source) -> None:
        _ = self._connection.execute(
            """
            INSERT INTO sources (
                source_id,
                source_kind,
                requested_locator,
                resolved_locator,
                canonical_locator,
                docset_root,
                active_snapshot_id,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                source_kind = excluded.source_kind,
                requested_locator = excluded.requested_locator,
                resolved_locator = excluded.resolved_locator,
                canonical_locator = excluded.canonical_locator,
                docset_root = excluded.docset_root,
                active_snapshot_id = excluded.active_snapshot_id,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                source.source_id,
                source.source_kind.value,
                source.requested_locator,
                source.resolved_locator,
                source.canonical_locator,
                source.docset_root,
                source.active_snapshot_id,
                source.created_at,
                source.updated_at,
            ),
        )
        self._connection.commit()

    def get_source(self, source_id: str) -> Source | None:
        row = cast(
            sqlite3.Row | None,
            self._connection.execute(
                "SELECT * FROM sources WHERE source_id = ?",
                (source_id,),
            ).fetchone(),
        )
        if row is None:
            return None
        return Source(
            source_id=cast(str, row["source_id"]),
            source_kind=SourceKind(cast(str, row["source_kind"])),
            requested_locator=cast(str, row["requested_locator"]),
            resolved_locator=cast(str | None, row["resolved_locator"]),
            canonical_locator=cast(str, row["canonical_locator"]),
            docset_root=cast(str, row["docset_root"]),
            active_snapshot_id=cast(str | None, row["active_snapshot_id"]),
            created_at=cast(str | None, row["created_at"]),
            updated_at=cast(str | None, row["updated_at"]),
        )

    def get_source_by_canonical_locator(self, canonical_locator: str) -> Source | None:
        row = cast(
            sqlite3.Row | None,
            self._connection.execute(
                "SELECT * FROM sources WHERE canonical_locator = ?",
                (canonical_locator,),
            ).fetchone(),
        )
        if row is None:
            return None
        return Source(
            source_id=cast(str, row["source_id"]),
            source_kind=SourceKind(cast(str, row["source_kind"])),
            requested_locator=cast(str, row["requested_locator"]),
            resolved_locator=cast(str | None, row["resolved_locator"]),
            canonical_locator=cast(str, row["canonical_locator"]),
            docset_root=cast(str, row["docset_root"]),
            active_snapshot_id=cast(str | None, row["active_snapshot_id"]),
            created_at=cast(str | None, row["created_at"]),
            updated_at=cast(str | None, row["updated_at"]),
        )

    def list_sources(self) -> list[Source]:
        rows = cast(
            list[sqlite3.Row],
            self._connection.execute(
                "SELECT * FROM sources ORDER BY canonical_locator ASC"
            ).fetchall(),
        )
        return [
            Source(
                source_id=cast(str, row["source_id"]),
                source_kind=SourceKind(cast(str, row["source_kind"])),
                requested_locator=cast(str, row["requested_locator"]),
                resolved_locator=cast(str | None, row["resolved_locator"]),
                canonical_locator=cast(str, row["canonical_locator"]),
                docset_root=cast(str, row["docset_root"]),
                active_snapshot_id=cast(str | None, row["active_snapshot_id"]),
                created_at=cast(str | None, row["created_at"]),
                updated_at=cast(str | None, row["updated_at"]),
            )
            for row in rows
        ]

    def insert_snapshot(self, snapshot: Snapshot) -> None:
        _ = self._connection.execute(
            """
            INSERT INTO snapshots (
                snapshot_id,
                source_id,
                status,
                fetched_at,
                content_hash,
                etag,
                last_modified,
                is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.snapshot_id,
                snapshot.source_id,
                snapshot.status.value,
                snapshot.fetched_at,
                snapshot.content_hash,
                snapshot.etag,
                snapshot.last_modified,
                int(snapshot.is_active),
            ),
        )
        self._connection.commit()

    def get_active_snapshot(self, source_id: str) -> Snapshot | None:
        row = cast(
            sqlite3.Row | None,
            self._connection.execute(
                "SELECT * FROM snapshots WHERE source_id = ? AND is_active = 1",
                (source_id,),
            ).fetchone(),
        )
        if row is None:
            return None
        return _snapshot_from_row(row)

    def count_documents(self, snapshot_id: str) -> int:
        row = cast(
            tuple[int] | None,
            self._connection.execute(
                "SELECT COUNT(*) FROM documents WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone(),
        )
        if row is None:
            return 0
        return row[0]

    def count_chunks(self, snapshot_id: str) -> int:
        row = cast(
            tuple[int] | None,
            self._connection.execute(
                "SELECT COUNT(*) FROM chunks WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone(),
        )
        if row is None:
            return 0
        return row[0]

    def replace_snapshot_documents(
        self,
        snapshot_id: str,
        source_id: str,
        documents: list[DiscoveredDocument],
    ) -> list[Document]:
        _ = self._connection.execute(
            "DELETE FROM documents WHERE snapshot_id = ?",
            (snapshot_id,),
        )
        stored_documents: list[Document] = []
        for index, document in enumerate(documents):
            document_id = f"{snapshot_id}-doc-{index}"
            metadata_json = json.dumps(document.metadata, sort_keys=True)
            _ = self._connection.execute(
                """
                INSERT INTO documents (
                    document_id,
                    source_id,
                    snapshot_id,
                    requested_locator,
                    resolved_locator,
                    canonical_locator,
                    title,
                    section_path,
                    content_hash,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    source_id,
                    snapshot_id,
                    document.requested_locator,
                    document.resolved_locator,
                    document.canonical_locator,
                    document.title,
                    json.dumps([], sort_keys=True),
                    document.content_hash,
                    metadata_json,
                ),
            )
            stored_documents.append(
                Document(
                    document_id=document_id,
                    source_id=source_id,
                    snapshot_id=snapshot_id,
                    requested_locator=document.requested_locator,
                    resolved_locator=document.resolved_locator,
                    canonical_locator=document.canonical_locator,
                    title=document.title,
                    section_path=(),
                    content_hash=document.content_hash,
                    metadata=dict(document.metadata),
                )
            )
        self._connection.commit()
        return stored_documents

    def list_documents(self, snapshot_id: str) -> list[Document]:
        rows = cast(
            list[sqlite3.Row],
            self._connection.execute(
                "SELECT * FROM documents WHERE snapshot_id = ? ORDER BY canonical_locator ASC",
                (snapshot_id,),
            ).fetchall(),
        )
        return [
            Document(
                document_id=cast(str, row["document_id"]),
                source_id=cast(str, row["source_id"]),
                snapshot_id=cast(str, row["snapshot_id"]),
                requested_locator=cast(str, row["requested_locator"]),
                resolved_locator=cast(str, row["resolved_locator"]),
                canonical_locator=cast(str, row["canonical_locator"]),
                title=cast(str | None, row["title"]),
                section_path=tuple(
                    cast(list[str], json.loads(cast(str, row["section_path"]) or "[]"))
                ),
                content_hash=cast(str | None, row["content_hash"]),
                metadata=cast(
                    dict[str, object],
                    json.loads(cast(str, row["metadata_json"]) or "{}"),
                ),
            )
            for row in rows
        ]

    def replace_snapshot_chunks(self, snapshot_id: str, chunks: list[Chunk]) -> None:
        _ = self._connection.execute(
            "DELETE FROM chunks WHERE snapshot_id = ?",
            (snapshot_id,),
        )
        for chunk in chunks:
            _ = self._connection.execute(
                """
                INSERT INTO chunks (
                    chunk_id,
                    source_id,
                    snapshot_id,
                    document_id,
                    chunk_index,
                    text,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    chunk.source_id,
                    chunk.snapshot_id,
                    chunk.document_id,
                    chunk.chunk_index,
                    chunk.text,
                    json.dumps(chunk.metadata, sort_keys=True),
                ),
            )
        self._rebuild_chunk_fts()
        self._connection.commit()

    def search_chunks(self, match_query: str, *, limit: int) -> list[QueryHit]:
        rows = cast(
            list[sqlite3.Row],
            self._connection.execute(
                """
                SELECT
                    chunks.source_id,
                    chunks.snapshot_id,
                    chunks.document_id,
                    chunks.chunk_id,
                    chunks.chunk_index,
                    chunks.text,
                    chunks.metadata_json,
                    bm25(chunk_fts) AS score
                FROM chunk_fts
                JOIN chunks ON chunks.rowid = chunk_fts.rowid
                JOIN snapshots ON snapshots.snapshot_id = chunks.snapshot_id
                WHERE chunk_fts MATCH ?
                  AND snapshots.is_active = 1
                ORDER BY
                    score ASC,
                    chunks.source_id ASC,
                    chunks.snapshot_id ASC,
                    chunks.document_id ASC,
                    chunks.chunk_index ASC
                LIMIT ?
                """,
                (match_query, limit),
            ).fetchall(),
        )
        return [
            QueryHit(
                source_id=cast(str, row["source_id"]),
                snapshot_id=cast(str, row["snapshot_id"]),
                document_id=cast(str, row["document_id"]),
                chunk_id=cast(str, row["chunk_id"]),
                chunk_index=cast(int, row["chunk_index"]),
                text=cast(str, row["text"]),
                score=float(cast(int | float, row["score"])),
                metadata=cast(
                    dict[str, object],
                    json.loads(cast(str, row["metadata_json"]) or "{}"),
                ),
            )
            for row in rows
        ]

    def activate_snapshot(self, source_id: str, snapshot_id: str) -> None:
        _ = self._connection.execute(
            "UPDATE snapshots SET is_active = 0 WHERE source_id = ?",
            (source_id,),
        )
        _ = self._connection.execute(
            "UPDATE snapshots SET is_active = 1, status = ? WHERE snapshot_id = ?",
            (SnapshotStatus.INDEXED.value, snapshot_id),
        )
        _ = self._connection.execute(
            "UPDATE sources SET active_snapshot_id = ? WHERE source_id = ?",
            (snapshot_id, source_id),
        )
        self._connection.commit()

    def mark_snapshot_failed(self, snapshot_id: str) -> None:
        _ = self._connection.execute(
            "UPDATE snapshots SET status = ?, is_active = 0 WHERE snapshot_id = ?",
            (SnapshotStatus.FAILED.value, snapshot_id),
        )
        self._connection.commit()

    def delete_source(self, source_id: str) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM sources WHERE source_id = ?", (source_id,)
        )
        removed = cursor.rowcount > 0
        if removed:
            self._rebuild_chunk_fts()
        self._connection.commit()
        return removed

    def _rebuild_chunk_fts(self) -> None:
        _ = self._connection.execute(
            "INSERT INTO chunk_fts(chunk_fts) VALUES ('rebuild')"
        )


def _snapshot_from_row(row: sqlite3.Row) -> Snapshot:
    return Snapshot(
        snapshot_id=cast(str, row["snapshot_id"]),
        source_id=cast(str, row["source_id"]),
        status=SnapshotStatus(cast(str, row["status"])),
        fetched_at=cast(str | None, row["fetched_at"]),
        content_hash=cast(str | None, row["content_hash"]),
        etag=cast(str | None, row["etag"]),
        last_modified=cast(str | None, row["last_modified"]),
        is_active=bool(cast(int, row["is_active"])),
    )

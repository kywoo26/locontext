from __future__ import annotations

import json
import re
import sqlite3
from typing import Final, cast
from urllib.parse import urlparse

from ..domain.models import (
    Chunk,
    DiscoveredDocument,
    Document,
    QueryHit,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
    SourceSet,
    SourceSetMember,
)
from .migrations import apply_migrations

_QUERY_TERM_PATTERN: Final[re.Pattern[str]] = re.compile(r"[0-9A-Za-z_]+")
_GITHUB_OPERATIONAL_TERMS: Final[frozenset[str]] = frozenset(
    {
        "agent",
        "agents",
        "claude",
        "command",
        "commands",
        "instructions",
        "llm",
        "llms",
        "prompt",
        "prompts",
        "workflow",
        "workflows",
    }
)
_GITHUB_MANAGEMENT_TERMS: Final[frozenset[str]] = frozenset(
    {
        "changelog",
        "compare",
        "issue",
        "issues",
        "milestone",
        "milestones",
        "note",
        "notes",
        "pr",
        "prs",
        "pull",
        "pulls",
        "release",
        "releases",
        "version",
        "versions",
    }
)


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

    def count_sources(self) -> int:
        row = cast(
            tuple[int] | None,
            self._connection.execute("SELECT COUNT(*) FROM sources").fetchone(),
        )
        return 0 if row is None else row[0]

    def count_source_sets(self) -> int:
        row = cast(
            tuple[int] | None,
            self._connection.execute("SELECT COUNT(*) FROM source_sets").fetchone(),
        )
        return 0 if row is None else row[0]

    def count_active_snapshots(self) -> int:
        row = cast(
            tuple[int] | None,
            self._connection.execute(
                "SELECT COUNT(*) FROM snapshots WHERE is_active = 1"
            ).fetchone(),
        )
        return 0 if row is None else row[0]

    def count_all_documents(self) -> int:
        row = cast(
            tuple[int] | None,
            self._connection.execute("SELECT COUNT(*) FROM documents").fetchone(),
        )
        return 0 if row is None else row[0]

    def count_all_chunks(self) -> int:
        row = cast(
            tuple[int] | None,
            self._connection.execute("SELECT COUNT(*) FROM chunks").fetchone(),
        )
        return 0 if row is None else row[0]

    def create_source_set(
        self,
        source_set_id: str,
        set_name: str,
        source_ids: list[str],
    ) -> SourceSet:
        with self._connection:
            _ = self._connection.execute(
                """
                INSERT INTO source_sets (source_set_id, set_name)
                VALUES (?, ?)
                ON CONFLICT(source_set_id) DO UPDATE SET
                    set_name = excluded.set_name
                """,
                (source_set_id, set_name),
            )
            _ = self._connection.execute(
                "DELETE FROM source_set_members WHERE source_set_id = ?",
                (source_set_id,),
            )
            for member_index, source_id in enumerate(source_ids):
                _ = self._connection.execute(
                    """
                    INSERT INTO source_set_members (
                        source_set_id,
                        source_id,
                        member_index
                    ) VALUES (?, ?, ?)
                    """,
                    (source_set_id, source_id, member_index),
                )
        return self.get_source_set_by_id(source_set_id) or SourceSet(
            source_set_id=source_set_id,
            set_name=set_name,
        )

    def list_source_sets(self) -> list[SourceSet]:
        rows = cast(
            list[sqlite3.Row],
            self._connection.execute(
                """
                SELECT source_set_id, set_name
                FROM source_sets
                ORDER BY set_name ASC, source_set_id ASC
                """
            ).fetchall(),
        )
        source_sets: list[SourceSet] = []
        for row in rows:
            source_set = self.get_source_set_by_id(cast(str, row["source_set_id"]))
            if source_set is not None:
                source_sets.append(source_set)
        return source_sets

    def get_source_set(self, set_name: str) -> SourceSet | None:
        row = cast(
            sqlite3.Row | None,
            self._connection.execute(
                """
                SELECT source_set_id, set_name
                FROM source_sets
                WHERE set_name = ?
                """,
                (set_name,),
            ).fetchone(),
        )
        if row is None:
            return None
        return self.get_source_set_by_id(cast(str, row["source_set_id"]))

    def get_source_set_by_id(self, source_set_id: str) -> SourceSet | None:
        set_row = cast(
            sqlite3.Row | None,
            self._connection.execute(
                """
                SELECT source_set_id, set_name
                FROM source_sets
                WHERE source_set_id = ?
                """,
                (source_set_id,),
            ).fetchone(),
        )
        if set_row is None:
            return None
        member_rows = cast(
            list[sqlite3.Row],
            self._connection.execute(
                """
                SELECT
                    source_set_members.source_id,
                    sources.canonical_locator,
                    source_set_members.member_index
                FROM source_set_members
                JOIN sources ON sources.source_id = source_set_members.source_id
                WHERE source_set_members.source_set_id = ?
                ORDER BY source_set_members.member_index ASC
                """,
                (source_set_id,),
            ).fetchall(),
        )
        return SourceSet(
            source_set_id=cast(str, set_row["source_set_id"]),
            set_name=cast(str, set_row["set_name"]),
            members=tuple(
                SourceSetMember(
                    source_id=cast(str, row["source_id"]),
                    canonical_locator=cast(str, row["canonical_locator"]),
                    member_index=cast(int, row["member_index"]),
                )
                for row in member_rows
            ),
        )

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

    def search_chunks(
        self,
        match_query: str,
        *,
        limit: int,
        source_id: str | None = None,
    ) -> list[QueryHit]:
        where_filter = "AND chunks.source_id = ?" if source_id is not None else ""
        parameters: tuple[object, ...]
        fetch_limit = max(limit * 10, limit) if limit > 0 else limit
        if source_id is None:
            parameters = (match_query, fetch_limit)
        else:
            parameters = (match_query, source_id, fetch_limit)
        rows = cast(
            list[sqlite3.Row],
            self._connection.execute(
                f"""
                SELECT
                    chunks.source_id,
                    chunks.snapshot_id,
                    chunks.document_id,
                    chunks.chunk_id,
                    chunks.chunk_index,
                    chunks.text,
                    chunks.metadata_json,
                    documents.canonical_locator AS document_locator,
                    sources.canonical_locator AS source_locator,
                    bm25(chunk_fts) AS score
                FROM chunk_fts
                JOIN chunks ON chunks.rowid = chunk_fts.rowid
                JOIN documents ON documents.document_id = chunks.document_id
                JOIN snapshots ON snapshots.snapshot_id = chunks.snapshot_id
                JOIN sources ON sources.source_id = chunks.source_id
                WHERE chunk_fts MATCH ?
                  AND snapshots.is_active = 1
                  {where_filter}
                ORDER BY
                    score ASC,
                    chunks.source_id ASC,
                    chunks.snapshot_id ASC,
                    chunks.document_id ASC,
                    chunks.chunk_index ASC
                LIMIT ?
                """,
                parameters,
            ).fetchall(),
        )
        ranked_rows = _rerank_github_repo_rows(match_query, rows)
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
            for row in ranked_rows[:limit]
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

    def mark_snapshot_stale(self, snapshot_id: str) -> None:
        _ = self._connection.execute(
            "UPDATE snapshots SET status = ? WHERE snapshot_id = ?",
            (SnapshotStatus.STALE.value, snapshot_id),
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


def _rerank_github_repo_rows(
    match_query: str, rows: list[sqlite3.Row]
) -> list[sqlite3.Row]:
    if len(rows) <= 1:
        return rows
    repo_roots = {
        repo_root
        for row in rows
        for repo_root in [_github_repo_root(cast(str, row["document_locator"]))]
        if repo_root is not None
    }
    if len(repo_roots) != 1:
        return rows
    if any(
        _github_repo_root(cast(str, row["document_locator"])) is None for row in rows
    ):
        return rows
    intent = _classify_github_query_intent(match_query)
    enumerated_rows = list(enumerate(rows))
    enumerated_rows.sort(
        key=lambda item: (
            _github_locator_rank(
                intent=intent,
                document_locator=cast(str, item[1]["document_locator"]),
            ),
            float(cast(int | float, item[1]["score"])),
            cast(str, item[1]["source_id"]),
            cast(str, item[1]["snapshot_id"]),
            cast(str, item[1]["document_id"]),
            cast(int, item[1]["chunk_index"]),
            item[0],
        )
    )
    return [row for _, row in enumerated_rows]


def _classify_github_query_intent(match_query: str) -> str:
    terms = cast(list[str], _QUERY_TERM_PATTERN.findall(match_query))
    normalized_query = " ".join(term.lower() for term in terms)
    query_terms = {term.lower() for term in terms}
    if query_terms & _GITHUB_MANAGEMENT_TERMS:
        return "repo-management"
    if (
        query_terms & _GITHUB_OPERATIONAL_TERMS
        or "how to work in this repo" in normalized_query
    ):
        return "repo-operational"
    return "repo-doc"


def _github_locator_rank(*, intent: str, document_locator: str) -> tuple[int, int]:
    category, subcategory = _github_document_category(document_locator)
    if intent == "repo-management":
        category_rank = {
            "management": 0,
            "guidance": 1,
            "readme": 2,
            "docs": 3,
            "wiki": 4,
            "repo-content": 5,
            "other": 6,
        }
    elif intent == "repo-operational":
        category_rank = {
            "guidance": 0,
            "readme": 1,
            "docs": 2,
            "wiki": 3,
            "repo-content": 4,
            "management": 5,
            "other": 6,
        }
    else:
        category_rank = {
            "readme": 0,
            "docs": 1,
            "repo-content": 2,
            "wiki": 3,
            "guidance": 4,
            "management": 5,
            "other": 6,
        }
    return (category_rank.get(category, 6), subcategory)


def _github_document_category(document_locator: str) -> tuple[str, int]:
    locator = document_locator.lower()
    if locator.endswith("/agents.md"):
        return ("guidance", 0)
    if locator.endswith("/claude.md"):
        return ("guidance", 1)
    if locator.endswith("/llms.txt"):
        return ("guidance", 2)
    if locator.endswith("/readme.md"):
        return ("readme", 0)
    management_category = _github_management_category(locator)
    if management_category is not None:
        return management_category
    if locator.endswith("/wiki") or "/wiki/" in locator:
        return ("wiki", 0)
    if "/docs/" in locator:
        return ("docs", 0)
    if _is_github_repo_content_locator(locator):
        return ("repo-content", 0)
    return ("other", 0)


def _is_github_repo_content_locator(locator: str) -> bool:
    return any(
        marker in locator
        for marker in ("/blob/", "/tree/", "raw.githubusercontent.com/")
    )


def _github_management_category(locator: str) -> tuple[str, int] | None:
    parsed = urlparse(locator)
    if parsed.netloc.lower() != "github.com":
        return None
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 3:
        return None
    family = path_parts[2]
    if family == "releases":
        return ("management", 0)
    if family == "issues":
        return ("management", 1)
    if family == "pulls":
        return ("management", 2)
    if family == "compare":
        return ("management", 3)
    return None


def _github_repo_root(locator: str) -> str | None:
    if "github.com/" in locator:
        _, _, suffix = locator.partition("github.com/")
    elif "raw.githubusercontent.com/" in locator:
        _, _, suffix = locator.partition("raw.githubusercontent.com/")
    else:
        return None
    parts = [part for part in suffix.split("/") if part]
    if len(parts) < 2:
        return None
    return "/".join(parts[:2])

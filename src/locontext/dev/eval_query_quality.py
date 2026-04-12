from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from typing import Final, cast

from ..app.query import query_local_json
from ..domain.models import (
    Chunk,
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from ..store.sqlite import SQLiteStore


@dataclass(slots=True, frozen=True)
class QueryQualityFixture:
    name: str
    query_text: str
    limit: int
    expected_hit_keys: tuple[str, ...]
    source_id: str | None = None


@dataclass(slots=True, frozen=True)
class QueryQualityResult:
    fixture: str
    hit_count: int
    expected_hit_count: int
    passed: bool
    actual_hit_keys: list[str]
    expected_hit_keys: list[str]


_FIXTURES: Final[dict[str, QueryQualityFixture]] = {
    "basic-docs": QueryQualityFixture(
        name="basic-docs",
        query_text="guide term",
        limit=5,
        expected_hit_keys=("source-1|https://docs.example.com/docs/guide|0",),
    ),
    "multi-page-docset": QueryQualityFixture(
        name="multi-page-docset",
        query_text="install term",
        limit=5,
        expected_hit_keys=(
            "source-1|https://docs.example.com/docs/install|0",
            "source-1|https://docs.example.com/docs/index|0",
        ),
    ),
}


def evaluate_fixture(fixture_name: str) -> QueryQualityResult:
    fixture = _FIXTURES[fixture_name]
    connection = sqlite3.connect(":memory:")
    try:
        store = SQLiteStore(connection)
        store.ensure_schema()
        _seed_fixture(store, fixture)
        envelope = query_local_json(
            store,
            fixture.query_text,
            limit=fixture.limit,
            source_id=fixture.source_id,
        )
    finally:
        connection.close()

    actual_hit_keys = [
        f"{hit.source_id}|{hit.document_locator}|{hit.chunk_index}"
        for hit in envelope.hits
    ]
    expected_hit_keys = list(fixture.expected_hit_keys)
    return QueryQualityResult(
        fixture=fixture.name,
        hit_count=envelope.hit_count,
        expected_hit_count=len(expected_hit_keys),
        passed=actual_hit_keys == expected_hit_keys,
        actual_hit_keys=actual_hit_keys,
        expected_hit_keys=expected_hit_keys,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run local query quality baseline checks."
    )
    _ = parser.add_argument(
        "--fixture", required=True, choices=sorted(_FIXTURES.keys())
    )
    args = parser.parse_args()

    fixture_name = cast(str, args.fixture)
    result = evaluate_fixture(fixture_name)
    print(f"fixture: {result.fixture}")
    print(f"passed: {str(result.passed).lower()}")
    print(f"expected_hit_count: {result.expected_hit_count}")
    print(f"actual_hit_count: {result.hit_count}")
    print(f"expected_hit_keys: {result.expected_hit_keys}")
    print(f"actual_hit_keys: {result.actual_hit_keys}")
    return 0 if result.passed else 1


def _seed_fixture(store: SQLiteStore, fixture: QueryQualityFixture) -> None:
    source = Source(
        source_id="source-1",
        source_kind=SourceKind.WEB,
        requested_locator="https://docs.example.com/docs",
        resolved_locator="https://docs.example.com/docs",
        canonical_locator="https://docs.example.com/docs",
        docset_root="https://docs.example.com/docs",
    )
    store.upsert_source(source)

    if fixture.name == "basic-docs":
        _insert_snapshot_with_chunks(
            store,
            source,
            snapshot_id="snapshot-basic",
            documents=(
                (
                    "https://docs.example.com/docs/guide",
                    ["Guide > Intro\nguide term alpha content"],
                ),
            ),
        )
        return

    if fixture.name == "multi-page-docset":
        _insert_snapshot_with_chunks(
            store,
            source,
            snapshot_id="snapshot-docset",
            documents=(
                (
                    "https://docs.example.com/docs/index",
                    ["Guide > Intro\ninstall term overview"],
                ),
                (
                    "https://docs.example.com/docs/install",
                    ["Guide > Install\ninstall term details"],
                ),
            ),
        )
        return

    raise KeyError(fixture.name)


def _insert_snapshot_with_chunks(
    store: SQLiteStore,
    source: Source,
    *,
    snapshot_id: str,
    documents: tuple[tuple[str, list[str]], ...],
) -> None:
    snapshot = Snapshot(
        snapshot_id=snapshot_id,
        source_id=source.source_id,
        status=SnapshotStatus.INDEXED,
        content_hash=f"hash-{snapshot_id}",
        is_active=True,
    )
    store.insert_snapshot(snapshot)
    discovered = [
        DiscoveredDocument(
            requested_locator=document_locator,
            resolved_locator=document_locator,
            canonical_locator=document_locator,
            title=document_locator.rsplit("/", maxsplit=1)[-1],
            content_hash=f"doc-hash-{index}",
        )
        for index, (document_locator, _) in enumerate(documents)
    ]
    stored_documents = store.replace_snapshot_documents(
        snapshot.snapshot_id,
        source.source_id,
        discovered,
    )
    chunks: list[Chunk] = []
    for document, (_, chunk_texts) in zip(stored_documents, documents, strict=True):
        for chunk_index, text in enumerate(chunk_texts):
            chunks.append(
                Chunk(
                    chunk_id=f"{document.document_id}-chunk-{chunk_index}",
                    source_id=source.source_id,
                    snapshot_id=snapshot.snapshot_id,
                    document_id=document.document_id,
                    chunk_index=chunk_index,
                    text=text,
                    metadata={},
                )
            )
    store.replace_snapshot_chunks(snapshot.snapshot_id, chunks)
    store.activate_snapshot(source.source_id, snapshot.snapshot_id)


if __name__ == "__main__":
    raise SystemExit(main())

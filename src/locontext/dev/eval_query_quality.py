from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path
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


@dataclass(slots=True, frozen=True)
class QueryQualityMetricsResult:
    fixture: str
    metrics: dict[str, float]
    passed: bool


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
    "noisy-source": QueryQualityFixture(
        name="noisy-source",
        query_text="api token",
        limit=5,
        expected_hit_keys=("source-1|https://docs.example.com/docs/api|0",),
    ),
    "source-filter": QueryQualityFixture(
        name="source-filter",
        query_text="guide term",
        limit=5,
        expected_hit_keys=("source-2|https://docs.example.com/other/guide|0",),
        source_id="source-2",
    ),
    "no-hit-query": QueryQualityFixture(
        name="no-hit-query",
        query_text="definitely-no-hit",
        limit=5,
        expected_hit_keys=(),
    ),
    "ambiguous-multi-hit": QueryQualityFixture(
        name="ambiguous-multi-hit",
        query_text="shared term",
        limit=5,
        expected_hit_keys=(
            "source-1|https://docs.example.com/docs/alpha|0",
            "source-1|https://docs.example.com/docs/beta|0",
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


def evaluate_fixture_metrics(fixture_name: str) -> QueryQualityMetricsResult:
    result = evaluate_fixture(fixture_name)
    actual = result.actual_hit_keys
    expected = result.expected_hit_keys
    recall_at_limit = (
        1.0
        if not expected
        else sum(1 for key in expected if key in actual) / len(expected)
    )
    mrr = 0.0
    for rank, key in enumerate(actual, start=1):
        if key in expected:
            mrr = 1.0 / rank
            break
    return QueryQualityMetricsResult(
        fixture=result.fixture,
        metrics={
            "mrr": mrr,
            "recall_at_limit": recall_at_limit,
        },
        passed=result.passed,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run local query quality baseline checks."
    )
    _ = parser.add_argument(
        "--fixture", required=True, choices=sorted(_FIXTURES.keys())
    )
    _ = parser.add_argument("--seed-project")
    _ = parser.add_argument("--metrics", action="store_true")
    args = parser.parse_args()

    fixture_name = cast(str, args.fixture)
    seed_project = cast(str | None, args.seed_project)
    metrics_mode = cast(bool, args.metrics)
    if seed_project is not None:
        seed_fixture_project(fixture_name, Path(seed_project))
        print(f"seeded_project: {seed_project}")
        return 0

    if metrics_mode:
        metrics = evaluate_fixture_metrics(fixture_name)
        print(f"fixture: {metrics.fixture}")
        print(f"passed: {str(metrics.passed).lower()}")
        print(f"metrics: {metrics.metrics}")
        return 0 if metrics.passed else 1

    result = evaluate_fixture(fixture_name)
    print(f"fixture: {result.fixture}")
    print(f"passed: {str(result.passed).lower()}")
    print(f"expected_hit_count: {result.expected_hit_count}")
    print(f"actual_hit_count: {result.hit_count}")
    print(f"expected_hit_keys: {result.expected_hit_keys}")
    print(f"actual_hit_keys: {result.actual_hit_keys}")
    return 0 if result.passed else 1


def _seed_fixture(store: SQLiteStore, fixture: QueryQualityFixture) -> None:
    if fixture.name == "basic-docs":
        source = _seed_source(
            store,
            source_id="source-1",
            locator="https://docs.example.com/docs",
        )
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
        source = _seed_source(
            store,
            source_id="source-1",
            locator="https://docs.example.com/docs",
        )
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

    if fixture.name == "noisy-source":
        source = _seed_source(
            store,
            source_id="source-1",
            locator="https://docs.example.com/docs",
        )
        _insert_snapshot_with_chunks(
            store,
            source,
            snapshot_id="snapshot-noisy",
            documents=(
                (
                    "https://docs.example.com/docs/api",
                    ["API > Tokens\napi token authentication"],
                ),
                (
                    "https://docs.example.com/docs/navigation",
                    ["Docs navigation links and generic links"],
                ),
            ),
        )
        return

    if fixture.name == "source-filter":
        _seed_source_filter_fixture(store)
        return

    if fixture.name == "no-hit-query":
        source = _seed_source(
            store,
            source_id="source-1",
            locator="https://docs.example.com/docs",
        )
        _insert_snapshot_with_chunks(
            store,
            source,
            snapshot_id="snapshot-no-hit",
            documents=(
                (
                    "https://docs.example.com/docs/guide",
                    ["Guide > Intro\nhello world only"],
                ),
            ),
        )
        return

    if fixture.name == "ambiguous-multi-hit":
        source = _seed_source(
            store,
            source_id="source-1",
            locator="https://docs.example.com/docs",
        )
        _insert_snapshot_with_chunks(
            store,
            source,
            snapshot_id="snapshot-ambiguous",
            documents=(
                (
                    "https://docs.example.com/docs/alpha",
                    ["Alpha > Intro\nshared term alpha"],
                ),
                (
                    "https://docs.example.com/docs/beta",
                    ["Beta > Intro\nshared term beta"],
                ),
            ),
        )
        return

    raise KeyError(fixture.name)


def seed_fixture_project(fixture_name: str, project_root: Path) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    config_path = project_root / "locontext.toml"
    if not config_path.exists():
        _ = config_path.write_text('data_dir = ".locontext"\n', encoding="utf-8")
    data_dir = project_root / ".locontext"
    data_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(data_dir / "locontext.db")
    try:
        store = SQLiteStore(connection)
        store.ensure_schema()
        _seed_fixture(store, _FIXTURES[fixture_name])
    finally:
        connection.close()


def _seed_source(store: SQLiteStore, *, source_id: str, locator: str) -> Source:
    source = Source(
        source_id=source_id,
        source_kind=SourceKind.WEB,
        requested_locator=locator,
        resolved_locator=locator,
        canonical_locator=locator,
        docset_root=locator,
    )
    store.upsert_source(source)
    return source


def _seed_source_filter_fixture(store: SQLiteStore) -> None:
    source1 = _seed_source(
        store,
        source_id="source-1",
        locator="https://docs.example.com/docs",
    )
    source2 = _seed_source(
        store,
        source_id="source-2",
        locator="https://docs.example.com/other",
    )
    _insert_snapshot_with_chunks(
        store,
        source1,
        snapshot_id="snapshot-source-1",
        documents=(
            (
                "https://docs.example.com/docs/guide",
                ["Guide > Intro\nguide term from source one"],
            ),
        ),
    )
    _insert_snapshot_with_chunks(
        store,
        source2,
        snapshot_id="snapshot-source-2",
        documents=(
            (
                "https://docs.example.com/other/guide",
                ["Guide > Intro\nguide term from source two"],
            ),
        ),
    )


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

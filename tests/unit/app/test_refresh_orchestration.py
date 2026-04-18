from collections.abc import Sequence
from hashlib import sha256
from importlib import import_module

import httpx
import pytest

from locontext.app.refresh import RefreshOrchestrator
from locontext.domain.models import (
    DiscoveredDocument,
    DiscoveryOutcome,
    Document,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


class _RecordingIndexingEngine:
    def __init__(self) -> None:
        super().__init__()
        self.reindex_calls: list[tuple[str, str, int]] = []
        self.remove_calls: list[str] = []

    def reindex_snapshot(
        self, source: Source, snapshot: Snapshot, documents: Sequence[Document]
    ) -> None:
        self.reindex_calls.append(
            (source.source_id, snapshot.snapshot_id, len(documents))
        )

    def remove_source(self, source_id: str) -> None:
        self.remove_calls.append(source_id)


class _StaticOutcomeDiscoveryProvider:
    def __init__(self, outcome: DiscoveryOutcome) -> None:
        self.outcome = outcome

    def discover(self, source: Source) -> DiscoveryOutcome:
        _ = source
        return self.outcome


@pytest.fixture()
def source(store: SQLiteStore) -> Source:
    result = Source(
        source_id="source-1",
        source_kind=SourceKind.WEB,
        requested_locator="https://docs.example.com/docs",
        resolved_locator="https://docs.example.com/docs",
        canonical_locator="https://docs.example.com/docs",
        docset_root="https://docs.example.com/docs",
    )
    store.upsert_source(result)
    return result


def _legacy_manifest_hash(documents: Sequence[DiscoveredDocument]) -> str:
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


def _make_orchestrator(
    store: SQLiteStore, responses: list[tuple[str, str]]
) -> tuple[RefreshOrchestrator, _RecordingIndexingEngine]:
    remaining = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        if not remaining:
            raise AssertionError(f"unexpected request: {request.url}")
        body, content_type = remaining.pop(0)
        return httpx.Response(
            200,
            headers={"content-type": content_type},
            text=body,
            request=request,
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, follow_redirects=True)
    provider_module = import_module("locontext.sources.web.provider")
    provider = provider_module.WebDiscoveryProvider(client=client)
    engine = _RecordingIndexingEngine()
    return (RefreshOrchestrator(store, provider, engine), engine)


def test_unchanged_refresh_reuses_active_snapshot(
    store: SQLiteStore, source: Source
) -> None:
    _ = source
    orchestrator, engine = _make_orchestrator(
        store,
        [
            (
                "<html><head><title>Intro</title></head><body>Hello world</body></html>",
                "text/html; charset=utf-8",
            ),
            (
                "<html><head><title>Intro</title></head><body>Hello world</body></html>",
                "text/html; charset=utf-8",
            ),
        ],
    )
    first = orchestrator.refresh_source("source-1")
    second = orchestrator.refresh_source("source-1")
    assert first.changed
    assert not second.changed
    assert first.snapshot_id == second.snapshot_id
    assert len(engine.reindex_calls) == 1
    if first.snapshot_id is None:
        raise AssertionError("expected a snapshot id")
    active = store.get_active_snapshot("source-1")
    if active is None:
        raise AssertionError("expected an active snapshot")
    assert active.fetched_at is not None
    stored_documents = store.list_documents(first.snapshot_id)
    assert len(stored_documents) == 1
    assert stored_documents[0].title == "Intro"
    assert stored_documents[0].content_hash is not None


def test_changed_refresh_creates_new_active_snapshot(
    store: SQLiteStore, source: Source
) -> None:
    _ = source
    orchestrator, engine = _make_orchestrator(
        store,
        [
            (
                "<html><head><title>Intro</title></head><body>Hello world</body></html>",
                "text/html; charset=utf-8",
            ),
            (
                "<html><head><title>Intro</title></head><body>Hello again</body></html>",
                "text/html; charset=utf-8",
            ),
        ],
    )
    first = orchestrator.refresh_source("source-1")
    second = orchestrator.refresh_source("source-1")
    active = store.get_active_snapshot("source-1")
    assert first.snapshot_id != second.snapshot_id
    if active is None:
        raise AssertionError("expected an active snapshot")
    assert active.snapshot_id == second.snapshot_id
    assert len(engine.reindex_calls) == 2


def test_github_refresh_reprocesses_legacy_snapshot_under_new_rules(
    store: SQLiteStore,
) -> None:
    github_source = Source(
        source_id="source-github",
        source_kind=SourceKind.WEB,
        requested_locator="https://github.com/example/project",
        resolved_locator="https://github.com/example/project",
        canonical_locator="https://github.com/example/project",
        docset_root="https://github.com/example/project",
    )
    store.upsert_source(github_source)
    readme = DiscoveredDocument(
        requested_locator="https://github.com/example/project",
        resolved_locator="https://github.com/example/project",
        canonical_locator="https://github.com/example/project",
        title="README",
        content_hash="hash-readme",
    )
    management = DiscoveredDocument(
        requested_locator="https://github.com/example/project/issues",
        resolved_locator="https://github.com/example/project/issues",
        canonical_locator="https://github.com/example/project/issues",
        title="Issues",
        content_hash="hash-issues",
    )
    legacy_snapshot = Snapshot(
        snapshot_id="legacy-github-snapshot",
        source_id=github_source.source_id,
        status=SnapshotStatus.INDEXED,
        fetched_at="2025-01-01T00:00:00+00:00",
        content_hash=_legacy_manifest_hash([readme]),
        is_active=True,
    )
    store.insert_snapshot(legacy_snapshot)
    _ = store.replace_snapshot_documents(
        legacy_snapshot.snapshot_id,
        github_source.source_id,
        [readme, management],
    )
    store.activate_snapshot(github_source.source_id, legacy_snapshot.snapshot_id)
    provider = _StaticOutcomeDiscoveryProvider(
        DiscoveryOutcome(documents=[readme, management])
    )
    engine = _RecordingIndexingEngine()
    orchestrator = RefreshOrchestrator(store, provider, engine)
    result = orchestrator.refresh_source(github_source.source_id)
    assert result.changed
    assert result.document_count == 2
    assert len(engine.reindex_calls) == 1
    active = store.get_active_snapshot(github_source.source_id)
    if active is None:
        raise AssertionError("expected an active snapshot")
    assert active.snapshot_id != legacy_snapshot.snapshot_id
    stored_documents = store.list_documents(active.snapshot_id)
    assert [document.canonical_locator for document in stored_documents] == [
        readme.canonical_locator,
        management.canonical_locator,
    ]


def test_reindex_source_uses_active_snapshot_without_discovery(
    store: SQLiteStore, source: Source
) -> None:
    _ = source
    orchestrator, engine = _make_orchestrator(
        store,
        [
            (
                "<html><head><title>Intro</title></head><body>Hello world</body></html>",
                "text/html; charset=utf-8",
            )
        ],
    )
    _ = orchestrator.refresh_source("source-1")
    result = orchestrator.reindex_source("source-1")
    assert result.document_count == 1
    assert len(engine.reindex_calls) == 2


def test_remove_source_deletes_local_state_and_invokes_engine(
    store: SQLiteStore, source: Source
) -> None:
    _ = source
    orchestrator, engine = _make_orchestrator(
        store,
        [
            (
                "<html><head><title>Intro</title></head><body>Hello world</body></html>",
                "text/html; charset=utf-8",
            )
        ],
    )
    _ = orchestrator.refresh_source("source-1")
    orchestrator.remove_source("source-1")
    assert engine.remove_calls == ["source-1"]
    assert store.get_source("source-1") is None


def test_refresh_succeeds_when_one_child_link_fails(
    store: SQLiteStore, source: Source
) -> None:
    _ = source
    outcome = DiscoveryOutcome(documents=[], warning_count=1, warning_samples=[])
    outcome.documents.append(
        __import__(
            "locontext.domain.models", fromlist=["DiscoveredDocument"]
        ).DiscoveredDocument(
            requested_locator="https://docs.example.com/docs/intro",
            resolved_locator="https://docs.example.com/docs/intro",
            canonical_locator="https://docs.example.com/docs/intro",
            content_hash="hash-1",
        )
    )
    provider = _StaticOutcomeDiscoveryProvider(outcome)
    engine = _RecordingIndexingEngine()
    orchestrator = RefreshOrchestrator(store, provider, engine)
    result = orchestrator.refresh_source("source-1")
    assert result.changed
    assert result.document_count == 1
    assert result.warning_count == 1


def test_refresh_reports_unhealthy_empty_for_zero_documents(
    store: SQLiteStore, source: Source
) -> None:
    _ = source
    outcome = DiscoveryOutcome(documents=[])
    provider = _StaticOutcomeDiscoveryProvider(outcome)
    engine = _RecordingIndexingEngine()
    orchestrator = RefreshOrchestrator(store, provider, engine)
    result = orchestrator.refresh_source("source-1")
    assert result.changed
    assert result.document_count == 0
    assert result.freshness_state == "unhealthy-empty"
    assert result.freshness_reason == "zero documents in active snapshot"


def test_refresh_keeps_seed_failure_fatal(store: SQLiteStore, source: Source) -> None:
    _ = source

    class _FatalProvider:
        def discover(self, source: Source) -> DiscoveryOutcome:
            _ = source
            raise RuntimeError("seed fetch failed")

    orchestrator = RefreshOrchestrator(
        store, _FatalProvider(), _RecordingIndexingEngine()
    )
    with pytest.raises(RuntimeError, match="seed fetch failed"):
        _ = orchestrator.refresh_source("source-1")

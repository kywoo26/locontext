import json
import sqlite3
from pathlib import Path

from click.testing import CliRunner

from locontext.cli.main import main
from locontext.domain.models import (
    DiscoveredDocument,
    Snapshot,
    SnapshotStatus,
    Source,
    SourceKind,
)
from locontext.store.sqlite import SQLiteStore


def _seed_query_state() -> None:
    data_dir = Path(".locontext")
    data_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(data_dir / "locontext.db")
    try:
        store = SQLiteStore(connection)
        store.ensure_schema()
        source = Source(
            source_id="source-1",
            source_kind=SourceKind.WEB,
            requested_locator="https://docs.example.com/docs",
            resolved_locator="https://docs.example.com/docs",
            canonical_locator="https://docs.example.com/docs",
            docset_root="https://docs.example.com/docs",
        )
        store.upsert_source(source)
        other_source = Source(
            source_id="source-2",
            source_kind=SourceKind.WEB,
            requested_locator="https://docs.example.com/other",
            resolved_locator="https://docs.example.com/other",
            canonical_locator="https://docs.example.com/other",
            docset_root="https://docs.example.com/other",
        )
        store.upsert_source(other_source)
        stale_snapshot = Snapshot(
            snapshot_id="snapshot-stale",
            source_id=source.source_id,
            status=SnapshotStatus.STALE,
            content_hash="hash-stale",
            is_active=False,
        )
        active_snapshot = Snapshot(
            snapshot_id="snapshot-active",
            source_id=source.source_id,
            status=SnapshotStatus.INDEXED,
            content_hash="hash-active",
            is_active=True,
        )
        store.insert_snapshot(stale_snapshot)
        _ = store.replace_snapshot_documents(
            stale_snapshot.snapshot_id,
            source.source_id,
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/stale",
                    resolved_locator="https://docs.example.com/docs/stale",
                    canonical_locator="https://docs.example.com/docs/stale",
                    title="Stale",
                    content_hash="doc-hash-stale",
                )
            ],
        )
        store.insert_snapshot(active_snapshot)
        _ = store.replace_snapshot_documents(
            active_snapshot.snapshot_id,
            source.source_id,
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/guide",
                    resolved_locator="https://docs.example.com/docs/guide",
                    canonical_locator="https://docs.example.com/docs/guide",
                    title="Guide",
                    content_hash="doc-hash-active",
                )
            ],
        )
        _ = connection.execute(
            "\n                INSERT INTO chunks (\n                    chunk_id,\n                    source_id,\n                    snapshot_id,\n                    document_id,\n                    chunk_index,\n                    text,\n                    metadata_json\n                ) VALUES (?, ?, ?, ?, ?, ?, ?)\n                ",
            (
                "snapshot-stale-doc-0-chunk-0",
                source.source_id,
                stale_snapshot.snapshot_id,
                "snapshot-stale-doc-0",
                0,
                "shared query text from stale content",
                "{}",
            ),
        )
        row = connection.execute(
            "SELECT rowid FROM chunks WHERE chunk_id = ?",
            ("snapshot-stale-doc-0-chunk-0",),
        ).fetchone()
        if row is None:
            raise AssertionError("expected stale chunk rowid")
        _ = connection.execute(
            "INSERT INTO chunk_fts(rowid, chunk_id, text) VALUES (?, ?, ?)",
            (
                row[0],
                "snapshot-stale-doc-0-chunk-0",
                "shared query text from stale content",
            ),
        )
        active_chunks = [
            "shared query text from active content",
            "shared query text second active hit",
        ]
        for chunk_index, text in enumerate(active_chunks):
            chunk_id = f"snapshot-active-doc-0-chunk-{chunk_index}"
            _ = connection.execute(
                "\n                    INSERT INTO chunks (\n                        chunk_id,\n                        source_id,\n                        snapshot_id,\n                        document_id,\n                        chunk_index,\n                        text,\n                        metadata_json\n                    ) VALUES (?, ?, ?, ?, ?, ?, ?)\n                    ",
                (
                    chunk_id,
                    source.source_id,
                    active_snapshot.snapshot_id,
                    "snapshot-active-doc-0",
                    chunk_index,
                    text,
                    "{}",
                ),
            )
            active_row = connection.execute(
                "SELECT rowid FROM chunks WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
            if active_row is None:
                raise AssertionError("expected active chunk rowid")
            _ = connection.execute(
                "INSERT INTO chunk_fts(rowid, chunk_id, text) VALUES (?, ?, ?)",
                (active_row[0], chunk_id, text),
            )
        connection.commit()
        store.activate_snapshot(source.source_id, active_snapshot.snapshot_id)
        other_snapshot = Snapshot(
            snapshot_id="snapshot-other",
            source_id=other_source.source_id,
            status=SnapshotStatus.INDEXED,
            content_hash="hash-other",
            is_active=True,
        )
        store.insert_snapshot(other_snapshot)
        _ = store.replace_snapshot_documents(
            other_snapshot.snapshot_id,
            other_source.source_id,
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/other/page",
                    resolved_locator="https://docs.example.com/other/page",
                    canonical_locator="https://docs.example.com/other/page",
                    title="Other Guide",
                    content_hash="doc-hash-other",
                )
            ],
        )
        _ = connection.execute(
            "\n                INSERT INTO chunks (\n                    chunk_id,\n                    source_id,\n                    snapshot_id,\n                    document_id,\n                    chunk_index,\n                    text,\n                    metadata_json\n                ) VALUES (?, ?, ?, ?, ?, ?, ?)\n                ",
            (
                "snapshot-other-doc-0-chunk-0",
                other_source.source_id,
                other_snapshot.snapshot_id,
                "snapshot-other-doc-0",
                0,
                "shared query text from other source content",
                '{"section_path": ["Other"]}',
            ),
        )
        other_row = connection.execute(
            "SELECT rowid FROM chunks WHERE chunk_id = ?",
            ("snapshot-other-doc-0-chunk-0",),
        ).fetchone()
        if other_row is None:
            raise AssertionError("expected other chunk rowid")
        _ = connection.execute(
            "INSERT INTO chunk_fts(rowid, chunk_id, text) VALUES (?, ?, ?)",
            (
                other_row[0],
                "snapshot-other-doc-0-chunk-0",
                "shared query text from other source content",
            ),
        )
        store.activate_snapshot(other_source.source_id, other_snapshot.snapshot_id)
        connection.commit()
    finally:
        connection.close()


def _seed_github_query_state() -> None:
    data_dir = Path(".locontext")
    data_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(data_dir / "locontext.db")
    try:
        store = SQLiteStore(connection)
        store.ensure_schema()
        source = Source(
            source_id="github-source",
            source_kind=SourceKind.WEB,
            requested_locator="https://github.com/code-yeongyu/oh-my-openagent",
            resolved_locator="https://github.com/code-yeongyu/oh-my-openagent",
            canonical_locator="https://github.com/code-yeongyu/oh-my-openagent",
            docset_root="https://github.com/code-yeongyu/oh-my-openagent",
        )
        store.upsert_source(source)
        snapshot = Snapshot(
            snapshot_id="snapshot-github",
            source_id=source.source_id,
            status=SnapshotStatus.INDEXED,
            content_hash="hash-github",
            is_active=True,
        )
        store.insert_snapshot(snapshot)
        stored_documents = store.replace_snapshot_documents(
            snapshot.snapshot_id,
            source.source_id,
            [
                DiscoveredDocument(
                    requested_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/README.md",
                    resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/README.md",
                    canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/README.md",
                    title="README",
                    content_hash="doc-hash-readme",
                ),
                DiscoveredDocument(
                    requested_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
                    resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
                    canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
                    title="AGENTS.md",
                    content_hash="doc-hash-agents",
                ),
                DiscoveredDocument(
                    requested_locator="https://github.com/code-yeongyu/oh-my-openagent/releases",
                    resolved_locator="https://github.com/code-yeongyu/oh-my-openagent/releases",
                    canonical_locator="https://github.com/code-yeongyu/oh-my-openagent/releases",
                    title="releases",
                    content_hash="doc-hash-releases",
                ),
            ],
        )
        chunk_texts = {
            "https://github.com/code-yeongyu/oh-my-openagent/blob/main/README.md": "README install api configuration how to use",
            "https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md": "AGENTS agent command workflow prompt how to work in this repo",
            "https://github.com/code-yeongyu/oh-my-openagent/releases": "agent agent agent command command workflow prompt release notes open issues pull request compare versions",
        }
        for index, document in enumerate(stored_documents):
            text = chunk_texts[document.canonical_locator]
            chunk_id = f"{document.document_id}-chunk-{index}"
            _ = connection.execute(
                "\n                    INSERT INTO chunks (\n                        chunk_id,\n                        source_id,\n                        snapshot_id,\n                        document_id,\n                        chunk_index,\n                        text,\n                        metadata_json\n                    ) VALUES (?, ?, ?, ?, ?, ?, ?)\n                    ",
                (
                    chunk_id,
                    source.source_id,
                    snapshot.snapshot_id,
                    document.document_id,
                    0,
                    text,
                    "{}",
                ),
            )
            row = connection.execute(
                "SELECT rowid FROM chunks WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
            if row is None:
                raise AssertionError("expected chunk rowid")
            _ = connection.execute(
                "INSERT INTO chunk_fts(rowid, chunk_id, text) VALUES (?, ?, ?)",
                (row[0], chunk_id, text),
            )
        connection.commit()
        store.activate_snapshot(source.source_id, snapshot.snapshot_id)
    finally:
        connection.close()


def test_query_reports_stable_empty_state(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["query", "definitely-no-hit", "--limit", "5"])
    assert result.exit_code == 0
    assert result.output == "No query results.\n"


def test_query_help_is_available(runner: CliRunner) -> None:
    result = runner.invoke(main, ["query", "--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "--limit INTEGER" in result.output
    assert "--source TEXT" in result.output
    assert "--json" in result.output


def test_query_reports_stable_success_output_for_active_hits_only(
    runner: CliRunner,
) -> None:
    with runner.isolated_filesystem():
        _seed_query_state()
        result = runner.invoke(main, ["query", "shared query text", "--limit", "1"])
    assert result.exit_code == 0
    assert result.output.strip().splitlines() == [
        "1. https://docs.example.com/docs",
        "   document: https://docs.example.com/docs/guide",
        "   section: none",
        "   snippet: shared query text from active content",
    ]


def test_query_source_filter_narrows_results(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _seed_query_state()
        result = runner.invoke(
            main,
            ["query", "shared query text", "--limit", "5", "--source", "source-2"],
        )
    assert result.exit_code == 0
    assert result.output.strip().splitlines() == [
        "1. https://docs.example.com/other",
        "   document: https://docs.example.com/other/page",
        "   section: Other",
        "   snippet: shared query text from other source content",
    ]


def test_query_json_reports_machine_readable_envelope(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _seed_query_state()
        result = runner.invoke(
            main, ["query", "shared query text", "--limit", "2", "--json"]
        )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["query"]["text"] == "shared query text"
    assert payload["query"]["limit"] == 2
    assert payload["query"]["source_id"] is None
    assert payload["hit_count"] == 2
    assert payload["hits"][0]["source_locator"] == "https://docs.example.com/docs"
    assert "snippet" in payload["hits"][0]
    assert payload["hits"][0]["matched_terms"] == ["shared", "query", "text"]
    assert payload["hits"][0]["match_query"] == '"shared" AND "query" AND "text"'


def test_query_json_source_filter_narrows_results(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _seed_query_state()
        result = runner.invoke(
            main,
            [
                "query",
                "shared query text",
                "--limit",
                "5",
                "--source",
                "source-2",
                "--json",
            ],
        )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["query"]["source_id"] == "source-2"
    assert payload["hit_count"] == 1
    assert payload["hits"][0]["source_id"] == "source-2"


def test_query_json_reports_stable_empty_result(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["query", "definitely-no-hit", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["hit_count"] == 0
    assert payload["hits"] == []


def test_query_json_prefers_github_guidance_over_releases_for_agent_intent(
    runner: CliRunner,
) -> None:
    with runner.isolated_filesystem():
        _seed_github_query_state()
        result = runner.invoke(main, ["query", "agent", "--limit", "5", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["hit_count"] == 2
    assert [hit["document_locator"] for hit in payload["hits"]] == [
        "https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
        "https://github.com/code-yeongyu/oh-my-openagent/releases",
    ]
    assert payload["hits"][0]["rank"] == 1
    assert (
        payload["hits"][0]["source_locator"]
        == "https://github.com/code-yeongyu/oh-my-openagent"
    )
    assert payload["hits"][0]["metadata"] == {}

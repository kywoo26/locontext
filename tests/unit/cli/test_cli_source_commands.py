import sqlite3
from pathlib import Path
from typing import cast

import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture

from locontext.cli.main import main
from locontext.domain.models import DiscoveryOutcome, Snapshot, Source


class _EmptyDiscoveryProvider:
    def discover(self, source: Source) -> DiscoveryOutcome:
        _ = source
        return DiscoveryOutcome(documents=[])


class _RecordingIndexingEngine:
    def __init__(self) -> None:
        self.reindex_calls: list[tuple[str, str, int]] = []

    def reindex_snapshot(
        self,
        source: Source,
        snapshot: Snapshot,
        documents: list[object],
    ) -> None:
        self.reindex_calls.append(
            (source.source_id, snapshot.snapshot_id, len(documents))
        )

    def remove_source(self, _source_id: str) -> None:
        return None


def _snapshot_id(source_id: str) -> str | None:
    with sqlite3.connect(".locontext/locontext.db") as connection:
        row = cast(
            tuple[str | None] | None,
            connection.execute(
                "SELECT active_snapshot_id FROM sources WHERE source_id = ?",
                (source_id,),
            ).fetchone(),
        )
    if row is None:
        raise AssertionError("expected a stored source row")
    return row[0]


def _snapshot_fetched_at(snapshot_id: str) -> str:
    with sqlite3.connect(".locontext/locontext.db") as connection:
        row = cast(
            tuple[str] | None,
            connection.execute(
                "SELECT fetched_at FROM snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone(),
        )
    if row is None:
        raise AssertionError("expected a stored snapshot row")
    return row[0]


def test_source_add_creates_default_local_db(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            main, ["source", "add", "https://docs.example.com/docs?utm_source=x#intro"]
        )

        assert result.exit_code == 0
        assert "created source:" in result.output
        assert "canonical locator: https://docs.example.com/docs" in result.output
        assert Path(".locontext/locontext.db").exists()


def test_source_add_is_idempotent_for_equivalent_urls(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        first = runner.invoke(
            main, ["source", "add", "https://docs.example.com/docs?utm_source=x#intro"]
        )
        second = runner.invoke(main, ["source", "add", "https://docs.example.com/docs"])

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert "created source:" in first.output
        assert "existing source:" in second.output


def test_source_list_reports_empty_state(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["source", "list"])

        assert result.exit_code == 0
        assert result.output == "No sources registered.\n"


def test_source_list_shows_registered_sources_in_stable_order(
    runner: CliRunner,
) -> None:
    with runner.isolated_filesystem():
        _ = runner.invoke(main, ["source", "add", "https://docs.example.com/docs/beta"])
        _ = runner.invoke(
            main, ["source", "add", "https://docs.example.com/docs/alpha"]
        )

        result = runner.invoke(main, ["source", "list"])

        assert result.exit_code == 0
        lines = result.output.strip().splitlines()
        assert len(lines) == 2
        assert "https://docs.example.com/docs/alpha" in lines[0]
        assert "https://docs.example.com/docs/beta" in lines[1]


def test_source_remove_reports_removed_source(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        add_result = runner.invoke(
            main, ["source", "add", "https://docs.example.com/docs"]
        )
        assert add_result.exit_code == 0
        source_id = add_result.output.splitlines()[0].split()[-1]

        result = runner.invoke(main, ["source", "remove", source_id])

        assert result.exit_code == 0
        assert result.output == f"removed source: {source_id}\n"


def test_source_remove_reports_missing_source(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["source", "remove", "missing-id"])

        assert result.exit_code == 0
        assert result.output == "source not found: missing-id\n"


def test_source_remove_help_works(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["source", "remove", "--help"])

        assert result.exit_code == 0
        assert "Remove a registered documentation source." in result.output


def test_source_status_reports_empty_state(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["source", "status"])

        assert result.exit_code == 0
        assert result.output == "No sources registered.\n"


def test_source_status_reports_freshness_for_unrefreshed_source(
    runner: CliRunner,
) -> None:
    with runner.isolated_filesystem():
        add_result = runner.invoke(
            main, ["source", "add", "https://docs.example.com/docs"]
        )
        assert add_result.exit_code == 0

        result = runner.invoke(main, ["source", "status"])

        assert result.exit_code == 0
        assert "freshness=never-refreshed" in result.output


def test_source_show_reports_missing_source(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["source", "show", "missing-id"])

        assert result.exit_code == 0
        assert result.output == "source not found: missing-id\n"


def test_source_show_reports_active_zero_document_snapshot(
    runner: CliRunner, mocker: MockerFixture
) -> None:
    with runner.isolated_filesystem():
        add_result = runner.invoke(
            main, ["source", "add", "https://docs.example.com/docs"]
        )
        assert add_result.exit_code == 0
        source_id = add_result.output.splitlines()[0].split()[-1]
        provider = _EmptyDiscoveryProvider()
        engine = _RecordingIndexingEngine()

        _ = mocker.patch(
            "locontext.app.refresh._default_discovery_provider", return_value=provider
        )
        _ = mocker.patch(
            "locontext.app.refresh._default_indexing_engine", return_value=engine
        )
        refresh_result = runner.invoke(main, ["source", "refresh", source_id])

        assert refresh_result.exit_code == 0
        snapshot_id = _snapshot_id(source_id)
        assert snapshot_id is not None
        fetched_at = _snapshot_fetched_at(snapshot_id)

        result = runner.invoke(main, ["source", "show", source_id])

        assert result.exit_code == 0
        assert result.output.strip().splitlines() == [
            f"source_id: {source_id}",
            "canonical_locator: https://docs.example.com/docs",
            "docset_root: https://docs.example.com",
            f"active_snapshot_id: {snapshot_id}",
            "snapshot_status: indexed",
            "document_count: 0",
            "chunk_count: 0",
            f"fetched_at: {fetched_at}",
            "freshness: unhealthy-empty",
            "freshness_reason: zero documents in active snapshot",
            "etag: none",
            "last_modified: none",
        ]


def test_source_add_honors_custom_data_dir(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _ = Path("locontext.toml").write_text(
            'data_dir = "custom-state"\n', encoding="utf-8"
        )

        result = runner.invoke(main, ["source", "add", "https://docs.example.com/docs"])

        assert result.exit_code == 0
        assert Path("custom-state/locontext.db").exists()
        connection = sqlite3.connect("custom-state/locontext.db")
        try:
            row = cast(
                tuple[int] | None,
                connection.execute("SELECT COUNT(*) FROM sources").fetchone(),
            )
        finally:
            connection.close()
        assert row is not None
        assert row[0] == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))

from pathlib import Path

from click.testing import CliRunner

from locontext.cli.main import main


def test_status_guides_user_when_project_is_uninitialized(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert result.output.strip().splitlines() == [
            "project status: uninitialized",
            "run `locontext init` to create project-local state",
        ]


def test_status_reports_initialized_project_after_init(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        init_result = runner.invoke(main, ["init"])
        assert init_result.exit_code == 0
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert result.output.strip().splitlines() == [
            f"project_root: {Path.cwd()}",
            f"config_path: {Path.cwd() / 'locontext.toml'}",
            f"data_dir: {Path.cwd() / '.locontext'}",
            "initialized: true",
            "source_count: 0",
            "source_set_count: 0",
            "active_snapshot_count: 0",
            "document_count: 0",
            "chunk_count: 0",
        ]


def test_status_reports_project_level_counts(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _ = runner.invoke(main, ["init"])
        add1 = runner.invoke(
            main, ["source", "add", "https://docs.example.com/docs/one"]
        )
        add2 = runner.invoke(
            main, ["source", "add", "https://docs.example.com/docs/two"]
        )
        assert add1.exit_code == 0
        assert add2.exit_code == 0
        source_ids = [
            add1.output.splitlines()[0].split()[-1],
            add2.output.splitlines()[0].split()[-1],
        ]
        _ = runner.invoke(main, ["source-set", "add", "docs", *source_ids])
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert result.output.strip().splitlines() == [
            f"project_root: {Path.cwd()}",
            f"config_path: {Path.cwd() / 'locontext.toml'}",
            f"data_dir: {Path.cwd() / '.locontext'}",
            "initialized: true",
            "source_count: 2",
            "source_set_count: 1",
            "active_snapshot_count: 0",
            "document_count: 0",
            "chunk_count: 0",
        ]

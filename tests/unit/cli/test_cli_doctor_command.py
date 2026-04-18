import sqlite3
from pathlib import Path

from click.testing import CliRunner

from locontext.cli.main import main


def test_doctor_reports_uninitialized_project(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code != 0
        assert result.output.strip().splitlines() == [
            "doctor: fail project initialization",
            "  - missing config: locontext.toml",
            "  - missing data dir: .locontext",
            "  - missing database: .locontext/locontext.db",
            "  - run `locontext init` to create project-local state",
        ]


def test_doctor_reports_healthy_initialized_project(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        init_result = runner.invoke(main, ["init"])
        assert init_result.exit_code == 0
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0
        assert result.output.strip().splitlines() == [
            "doctor: ok project initialization",
            "  - config present: locontext.toml",
            "  - data dir present: .locontext",
            "  - database present: .locontext/locontext.db",
            "  - schema migrations table present",
            "  - core tables present",
        ]


def test_doctor_reports_broken_local_state(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        init_result = runner.invoke(main, ["init"])
        assert init_result.exit_code == 0
        db_path = Path(".locontext/locontext.db")
        with sqlite3.connect(db_path) as connection:
            connection.execute("DROP TABLE sources")
            connection.commit()
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code != 0
        assert result.output.strip().splitlines() == [
            "doctor: fail local state",
            "  - state error: no such table: sources",
        ]

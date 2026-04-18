import sqlite3
from pathlib import Path

from click.testing import CliRunner

from locontext.cli.main import main


def test_init_creates_config_and_local_state(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert result.output.strip().splitlines() == [
            "created config: locontext.toml",
            "created data dir: .locontext",
            "initialized database: .locontext/locontext.db",
        ]
        assert Path("locontext.toml").exists()
        assert Path(".locontext/locontext.db").exists()
        with sqlite3.connect(".locontext/locontext.db") as connection:
            row = connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchone()
        assert row == ("0001_initial.sql",)


def test_init_is_idempotent(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        first = runner.invoke(main, ["init"])
        second = runner.invoke(main, ["init"])
        assert first.exit_code == 0
        assert second.exit_code == 0
        assert second.output.strip().splitlines() == [
            "config already exists: locontext.toml",
            "data dir already exists: .locontext",
            "database already initialized: .locontext/locontext.db",
        ]

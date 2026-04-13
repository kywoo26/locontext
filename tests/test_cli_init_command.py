from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from click.testing import CliRunner

from locontext.cli.main import main


class InitCommandTest(unittest.TestCase):
    runner: CliRunner = CliRunner()

    def test_init_creates_config_and_local_state(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["init"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.output.strip().splitlines(),
                [
                    "created config: locontext.toml",
                    "created data dir: .locontext",
                    "initialized database: .locontext/locontext.db",
                ],
            )
            self.assertTrue(Path("locontext.toml").exists())
            self.assertTrue(Path(".locontext/locontext.db").exists())
            with sqlite3.connect(".locontext/locontext.db") as connection:
                row = connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchone()
            self.assertEqual(row, ("0001_initial.sql",))

    def test_init_is_idempotent(self) -> None:
        with self.runner.isolated_filesystem():
            first = self.runner.invoke(main, ["init"])
            second = self.runner.invoke(main, ["init"])

            self.assertEqual(first.exit_code, 0)
            self.assertEqual(second.exit_code, 0)
            self.assertEqual(
                second.output.strip().splitlines(),
                [
                    "config already exists: locontext.toml",
                    "data dir already exists: .locontext",
                    "database already initialized: .locontext/locontext.db",
                ],
            )


if __name__ == "__main__":
    _ = unittest.main()

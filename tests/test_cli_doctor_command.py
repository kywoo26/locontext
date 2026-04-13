from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from click.testing import CliRunner

from locontext.cli.main import main


class DoctorCommandTest(unittest.TestCase):
    runner: CliRunner = CliRunner()

    def test_doctor_reports_uninitialized_project(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["doctor"])

            self.assertNotEqual(result.exit_code, 0)
            self.assertEqual(
                result.output.strip().splitlines(),
                [
                    "doctor: fail project initialization",
                    "  - missing config: locontext.toml",
                    "  - missing data dir: .locontext",
                    "  - missing database: .locontext/locontext.db",
                    "  - run `locontext init` to create project-local state",
                ],
            )

    def test_doctor_reports_healthy_initialized_project(self) -> None:
        with self.runner.isolated_filesystem():
            init_result = self.runner.invoke(main, ["init"])
            self.assertEqual(init_result.exit_code, 0)

            result = self.runner.invoke(main, ["doctor"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.output.strip().splitlines(),
                [
                    "doctor: ok project initialization",
                    "  - config present: locontext.toml",
                    "  - data dir present: .locontext",
                    "  - database present: .locontext/locontext.db",
                    "  - schema migrations table present",
                    "  - core tables present",
                ],
            )

    def test_doctor_reports_broken_local_state(self) -> None:
        with self.runner.isolated_filesystem():
            init_result = self.runner.invoke(main, ["init"])
            self.assertEqual(init_result.exit_code, 0)
            db_path = Path(".locontext/locontext.db")
            with sqlite3.connect(db_path) as connection:
                connection.execute("DROP TABLE sources")
                connection.commit()

            result = self.runner.invoke(main, ["doctor"])

            self.assertNotEqual(result.exit_code, 0)
            self.assertEqual(
                result.output.strip().splitlines(),
                [
                    "doctor: fail local state",
                    "  - state error: no such table: sources",
                ],
            )


if __name__ == "__main__":
    _ = unittest.main()

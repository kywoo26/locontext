from __future__ import annotations

import unittest
from pathlib import Path

from click.testing import CliRunner

from locontext.cli.main import main


class StatusCommandTest(unittest.TestCase):
    runner: CliRunner = CliRunner()

    def test_status_guides_user_when_project_is_uninitialized(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["status"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.output.strip().splitlines(),
                [
                    "project status: uninitialized",
                    "run `locontext init` to create project-local state",
                ],
            )

    def test_status_reports_initialized_project_after_init(self) -> None:
        with self.runner.isolated_filesystem():
            init_result = self.runner.invoke(main, ["init"])
            self.assertEqual(init_result.exit_code, 0)

            result = self.runner.invoke(main, ["status"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.output.strip().splitlines(),
                [
                    f"project_root: {Path.cwd()}",
                    f"config_path: {Path.cwd() / 'locontext.toml'}",
                    f"data_dir: {Path.cwd() / '.locontext'}",
                    "initialized: true",
                ],
            )


if __name__ == "__main__":
    _ = unittest.main()

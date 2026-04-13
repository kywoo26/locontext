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
                    "source_count: 0",
                    "source_set_count: 0",
                    "active_snapshot_count: 0",
                    "document_count: 0",
                    "chunk_count: 0",
                ],
            )

    def test_status_reports_project_level_counts(self) -> None:
        with self.runner.isolated_filesystem():
            _ = self.runner.invoke(main, ["init"])
            add1 = self.runner.invoke(
                main, ["source", "add", "https://docs.example.com/docs/one"]
            )
            add2 = self.runner.invoke(
                main, ["source", "add", "https://docs.example.com/docs/two"]
            )
            self.assertEqual(add1.exit_code, 0)
            self.assertEqual(add2.exit_code, 0)
            source_ids = [
                add1.output.splitlines()[0].split()[-1],
                add2.output.splitlines()[0].split()[-1],
            ]
            _ = self.runner.invoke(main, ["source-set", "add", "docs", *source_ids])

            result = self.runner.invoke(main, ["status"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.output.strip().splitlines(),
                [
                    f"project_root: {Path.cwd()}",
                    f"config_path: {Path.cwd() / 'locontext.toml'}",
                    f"data_dir: {Path.cwd() / '.locontext'}",
                    "initialized: true",
                    "source_count: 2",
                    "source_set_count: 1",
                    "active_snapshot_count: 0",
                    "document_count: 0",
                    "chunk_count: 0",
                ],
            )


if __name__ == "__main__":
    _ = unittest.main()

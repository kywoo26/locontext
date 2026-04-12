from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from click.testing import CliRunner

from locontext.cli.main import main


class SourceCommandTest(unittest.TestCase):
    runner: CliRunner = CliRunner()

    def test_source_add_creates_default_local_db(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(
                main,
                ["source", "add", "https://docs.example.com/docs?utm_source=x#intro"],
            )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("created source:", result.output)
            self.assertIn(
                "canonical locator: https://docs.example.com/docs", result.output
            )
            self.assertTrue(Path(".locontext/locontext.db").exists())

    def test_source_add_is_idempotent_for_equivalent_urls(self) -> None:
        with self.runner.isolated_filesystem():
            first = self.runner.invoke(
                main,
                ["source", "add", "https://docs.example.com/docs?utm_source=x#intro"],
            )
            second = self.runner.invoke(
                main,
                ["source", "add", "https://docs.example.com/docs"],
            )

            self.assertEqual(first.exit_code, 0)
            self.assertEqual(second.exit_code, 0)
            self.assertIn("created source:", first.output)
            self.assertIn("existing source:", second.output)

    def test_source_list_reports_empty_state(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["source", "list"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, "No sources registered.\n")

    def test_source_list_shows_registered_sources_in_stable_order(self) -> None:
        with self.runner.isolated_filesystem():
            _ = self.runner.invoke(
                main, ["source", "add", "https://docs.example.com/docs/beta"]
            )
            _ = self.runner.invoke(
                main, ["source", "add", "https://docs.example.com/docs/alpha"]
            )

            result = self.runner.invoke(main, ["source", "list"])

            self.assertEqual(result.exit_code, 0)
            lines = result.output.strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn("https://docs.example.com/docs/alpha", lines[0])
            self.assertIn("https://docs.example.com/docs/beta", lines[1])

    def test_source_remove_reports_removed_source(self) -> None:
        with self.runner.isolated_filesystem():
            add_result = self.runner.invoke(
                main, ["source", "add", "https://docs.example.com/docs"]
            )
            self.assertEqual(add_result.exit_code, 0)
            source_id = add_result.output.splitlines()[0].split()[-1]

            result = self.runner.invoke(main, ["source", "remove", source_id])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, f"removed source: {source_id}\n")

    def test_source_remove_reports_missing_source(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["source", "remove", "missing-id"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, "source not found: missing-id\n")

    def test_source_remove_help_works(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["source", "remove", "--help"])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Remove a registered documentation source.", result.output)

    def test_source_add_honors_custom_data_dir(self) -> None:
        with self.runner.isolated_filesystem():
            Path("locontext.toml").write_text(
                'data_dir = "custom-state"\n', encoding="utf-8"
            )

            result = self.runner.invoke(
                main, ["source", "add", "https://docs.example.com/docs"]
            )

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(Path("custom-state/locontext.db").exists())
            connection = sqlite3.connect("custom-state/locontext.db")
            try:
                row = connection.execute("SELECT COUNT(*) FROM sources").fetchone()
            finally:
                connection.close()
            self.assertEqual(row[0], 1)


if __name__ == "__main__":
    unittest.main()

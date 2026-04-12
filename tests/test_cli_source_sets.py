from __future__ import annotations

import unittest

from click.testing import CliRunner

from locontext.cli.main import main  # pyright: ignore[reportMissingTypeStubs]


class SourceSetCommandTest(unittest.TestCase):
    runner: CliRunner = CliRunner()

    def _add_source(self, locator: str) -> str:
        result = self.runner.invoke(main, ["source", "add", locator])
        self.assertEqual(result.exit_code, 0)
        return result.output.splitlines()[0].split()[-1]

    def test_source_set_add_reports_created_set(self) -> None:
        with self.runner.isolated_filesystem():
            alpha_id = self._add_source("https://docs.example.com/alpha")
            beta_id = self._add_source("https://docs.example.com/beta")

            result = self.runner.invoke(
                main,
                ["source-set", "add", "docs", alpha_id, beta_id],
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.output,
                "created source set: docs\n" + f"source_ids: {alpha_id}, {beta_id}\n",
            )

    def test_source_set_add_reports_missing_sources_without_error(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(
                main,
                ["source-set", "add", "docs", "missing-id"],
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.output,
                "Sources not found for source set 'docs': missing-id\n",
            )

    def test_source_set_list_reports_empty_state(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["source-set", "list"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, "No source sets registered.\n")

    def test_source_set_list_shows_sets_in_stable_order(self) -> None:
        with self.runner.isolated_filesystem():
            alpha_id = self._add_source("https://docs.example.com/alpha")
            beta_id = self._add_source("https://docs.example.com/beta")

            _ = self.runner.invoke(main, ["source-set", "add", "zeta", beta_id])
            _ = self.runner.invoke(main, ["source-set", "add", "alpha", alpha_id])

            result = self.runner.invoke(main, ["source-set", "list"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.output,
                "set_name: alpha\n"
                + f"source_ids: {alpha_id}\n"
                + "\n"
                + "set_name: zeta\n"
                + f"source_ids: {beta_id}\n",
            )

    def test_source_set_show_reports_missing_set_without_error(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["source-set", "show", "docs"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, "source set not found: docs\n")

    def test_source_set_show_renders_members_deterministically(self) -> None:
        with self.runner.isolated_filesystem():
            alpha_id = self._add_source("https://docs.example.com/alpha")
            beta_id = self._add_source("https://docs.example.com/beta")

            _ = self.runner.invoke(
                main,
                ["source-set", "add", "docs", alpha_id, beta_id],
            )

            result = self.runner.invoke(main, ["source-set", "show", "docs"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.output,
                "set_name: docs\n"
                + "member_count: 2\n"
                + "members:\n"
                + f"  - [0] {alpha_id} https://docs.example.com/alpha\n"
                + f"  - [1] {beta_id} https://docs.example.com/beta\n",
            )

    def test_source_set_help_works(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["source-set", "--help"])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Manage named source sets.", result.output)


if __name__ == "__main__":
    _ = unittest.main()

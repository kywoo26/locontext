from __future__ import annotations

import tempfile
import unittest
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast


class _BaselineResult(Protocol):
    fixture: str
    hit_count: int
    expected_hit_count: int
    passed: bool
    actual_hit_keys: list[str]
    expected_hit_keys: list[str]


class _EvaluateFixture(Protocol):
    def __call__(self, fixture_name: str) -> _BaselineResult: ...


class _SeedFixtureProject(Protocol):
    def __call__(self, fixture_name: str, project_root: Path) -> None: ...


class QueryQualityBaselineContractTest(unittest.TestCase):
    def _evaluate(self, fixture_name: str) -> _BaselineResult:
        try:
            module = import_module("locontext.dev.eval_query_quality")
        except ModuleNotFoundError as exc:
            self.fail(f"expected locontext.dev.eval_query_quality module: {exc}")

        evaluate_fixture = cast(
            _EvaluateFixture | None,
            getattr(module, "evaluate_fixture", None),
        )
        if evaluate_fixture is None:
            self.fail("expected locontext.dev.eval_query_quality.evaluate_fixture")
        return evaluate_fixture(fixture_name)

    def _seed_project(self, fixture_name: str, project_root: Path) -> None:
        module = import_module("locontext.dev.eval_query_quality")
        seed_project = cast(
            _SeedFixtureProject | None,
            getattr(module, "seed_fixture_project", None),
        )
        if seed_project is None:
            self.fail("expected locontext.dev.eval_query_quality.seed_fixture_project")
        seed_project(fixture_name, project_root)

    def test_basic_docs_fixture_has_expected_hit_order(self) -> None:
        result = self._evaluate("basic-docs")

        self.assertEqual(result.fixture, "basic-docs")
        self.assertEqual(result.expected_hit_count, 1)
        self.assertEqual(result.actual_hit_keys, result.expected_hit_keys)
        self.assertEqual(
            result.expected_hit_keys,
            ["source-1|https://docs.example.com/docs/guide|0"],
        )
        self.assertTrue(result.passed)

    def test_multi_page_docset_fixture_has_expected_hit_order(self) -> None:
        result = self._evaluate("multi-page-docset")

        self.assertEqual(result.fixture, "multi-page-docset")
        self.assertEqual(result.expected_hit_count, 2)
        self.assertEqual(result.actual_hit_keys, result.expected_hit_keys)
        self.assertEqual(
            result.expected_hit_keys,
            [
                "source-1|https://docs.example.com/docs/install|0",
                "source-1|https://docs.example.com/docs/index|0",
            ],
        )
        self.assertTrue(result.passed)

    def test_noisy_source_fixture_is_available(self) -> None:
        result = self._evaluate("noisy-source")

        self.assertEqual(result.fixture, "noisy-source")
        self.assertTrue(result.passed)

    def test_source_filter_fixture_is_available(self) -> None:
        result = self._evaluate("source-filter")

        self.assertEqual(result.fixture, "source-filter")
        self.assertTrue(result.passed)

    def test_no_hit_query_fixture_is_available(self) -> None:
        result = self._evaluate("no-hit-query")

        self.assertEqual(result.fixture, "no-hit-query")
        self.assertTrue(result.passed)
        self.assertEqual(result.expected_hit_count, 0)

    def test_ambiguous_multi_hit_fixture_is_available(self) -> None:
        result = self._evaluate("ambiguous-multi-hit")

        self.assertEqual(result.fixture, "ambiguous-multi-hit")
        self.assertTrue(result.passed)
        self.assertGreaterEqual(result.expected_hit_count, 2)

    def test_source_filter_fixture_can_seed_project_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            self._seed_project("source-filter", project_root)

            self.assertTrue((project_root / ".locontext" / "locontext.db").exists())

    def test_unknown_fixture_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            _ = self._evaluate("missing-fixture")


if __name__ == "__main__":
    _ = unittest.main()

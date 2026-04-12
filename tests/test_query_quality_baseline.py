from __future__ import annotations

import unittest
from importlib import import_module
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

    def test_unknown_fixture_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            _ = self._evaluate("missing-fixture")


if __name__ == "__main__":
    _ = unittest.main()

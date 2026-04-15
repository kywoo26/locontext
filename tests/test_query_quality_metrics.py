from __future__ import annotations

import unittest
from importlib import import_module
from typing import Protocol, cast


class _MetricsResult(Protocol):
    fixture: str
    metrics: dict[str, float]
    passed: bool


class _EvaluateFixtureMetrics(Protocol):
    def __call__(self, fixture_name: str) -> _MetricsResult: ...


class QueryQualityMetricsContractTest(unittest.TestCase):
    def _evaluate_metrics(self, fixture_name: str) -> _MetricsResult:
        try:
            module = import_module("locontext.dev.eval_query_quality")
        except ModuleNotFoundError as exc:
            self.fail(f"expected locontext.dev.eval_query_quality module: {exc}")

        evaluate_metrics = cast(
            _EvaluateFixtureMetrics | None,
            getattr(module, "evaluate_fixture_metrics", None),
        )
        if evaluate_metrics is None:
            self.fail(
                "expected locontext.dev.eval_query_quality.evaluate_fixture_metrics"
            )
        return evaluate_metrics(fixture_name)

    def test_basic_docs_metrics_include_ordered_and_recall_like_values(self) -> None:
        result = self._evaluate_metrics("basic-docs")

        self.assertEqual(result.fixture, "basic-docs")
        self.assertTrue(result.passed)
        self.assertIn("mrr", result.metrics)
        self.assertIn("recall_at_limit", result.metrics)
        self.assertEqual(result.metrics["mrr"], 1.0)
        self.assertEqual(result.metrics["recall_at_limit"], 1.0)

    def test_multi_page_metrics_are_deterministic(self) -> None:
        first = self._evaluate_metrics("multi-page-docset")
        second = self._evaluate_metrics("multi-page-docset")

        self.assertEqual(first.metrics, second.metrics)
        self.assertTrue(first.passed)


if __name__ == "__main__":
    _ = unittest.main()

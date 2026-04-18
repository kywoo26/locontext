from importlib import import_module
from typing import Protocol, cast


class _MetricsResult(Protocol):
    fixture: str
    metrics: dict[str, float]
    passed: bool


class _EvaluateFixtureMetrics(Protocol):
    def __call__(self, fixture_name: str) -> _MetricsResult: ...


class TestQueryQualityMetricsContract:
    def _evaluate_metrics(self, fixture_name: str) -> _MetricsResult:
        try:
            module = import_module("locontext.dev.eval_query_quality")
        except ModuleNotFoundError as exc:
            raise AssertionError(
                f"expected locontext.dev.eval_query_quality module: {exc}"
            ) from exc
        evaluate_metrics = cast(
            _EvaluateFixtureMetrics | None,
            getattr(module, "evaluate_fixture_metrics", None),
        )
        if evaluate_metrics is None:
            raise AssertionError(
                "expected locontext.dev.eval_query_quality.evaluate_fixture_metrics"
            )
        return evaluate_metrics(fixture_name)

    def test_basic_docs_metrics_include_ordered_and_recall_like_values(self) -> None:
        result = self._evaluate_metrics("basic-docs")
        assert result.fixture == "basic-docs"
        assert result.passed
        assert "mrr" in result.metrics
        assert "recall_at_limit" in result.metrics
        assert result.metrics["mrr"] == 1.0
        assert result.metrics["recall_at_limit"] == 1.0

    def test_multi_page_metrics_are_deterministic(self) -> None:
        first = self._evaluate_metrics("multi-page-docset")
        second = self._evaluate_metrics("multi-page-docset")
        assert first.metrics == second.metrics
        assert first.passed

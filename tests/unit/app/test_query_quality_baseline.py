import tempfile
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

import pytest


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


class TestQueryQualityBaselineContract:
    def _evaluate(self, fixture_name: str) -> _BaselineResult:
        try:
            module = import_module("locontext.dev.eval_query_quality")
        except ModuleNotFoundError as exc:
            raise AssertionError(
                f"expected locontext.dev.eval_query_quality module: {exc}"
            ) from exc
        evaluate_fixture = cast(
            _EvaluateFixture | None, getattr(module, "evaluate_fixture", None)
        )
        if evaluate_fixture is None:
            raise AssertionError(
                "expected locontext.dev.eval_query_quality.evaluate_fixture"
            )
        return evaluate_fixture(fixture_name)

    def _seed_project(self, fixture_name: str, project_root: Path) -> None:
        module = import_module("locontext.dev.eval_query_quality")
        seed_project = cast(
            _SeedFixtureProject | None, getattr(module, "seed_fixture_project", None)
        )
        if seed_project is None:
            raise AssertionError(
                "expected locontext.dev.eval_query_quality.seed_fixture_project"
            )
        seed_project(fixture_name, project_root)

    def test_basic_docs_fixture_has_expected_hit_order(self) -> None:
        result = self._evaluate("basic-docs")
        assert result.fixture == "basic-docs"
        assert result.expected_hit_count == 1
        assert result.actual_hit_keys == result.expected_hit_keys
        assert result.expected_hit_keys == [
            "source-1|https://docs.example.com/docs/guide|0"
        ]
        assert result.passed

    def test_multi_page_docset_fixture_has_expected_hit_order(self) -> None:
        result = self._evaluate("multi-page-docset")
        assert result.fixture == "multi-page-docset"
        assert result.expected_hit_count == 2
        assert result.actual_hit_keys == result.expected_hit_keys
        assert result.expected_hit_keys == [
            "source-1|https://docs.example.com/docs/install|0",
            "source-1|https://docs.example.com/docs/index|0",
        ]
        assert result.passed

    def test_noisy_source_fixture_is_available(self) -> None:
        result = self._evaluate("noisy-source")
        assert result.fixture == "noisy-source"
        assert result.passed

    def test_source_filter_fixture_is_available(self) -> None:
        result = self._evaluate("source-filter")
        assert result.fixture == "source-filter"
        assert result.passed

    def test_no_hit_query_fixture_is_available(self) -> None:
        result = self._evaluate("no-hit-query")
        assert result.fixture == "no-hit-query"
        assert result.passed
        assert result.expected_hit_count == 0

    def test_ambiguous_multi_hit_fixture_is_available(self) -> None:
        result = self._evaluate("ambiguous-multi-hit")
        assert result.fixture == "ambiguous-multi-hit"
        assert result.passed
        assert result.expected_hit_count >= 2

    def test_source_filter_fixture_can_seed_project_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            self._seed_project("source-filter", project_root)
            assert (project_root / ".locontext" / "locontext.db").exists()

    def test_unknown_fixture_is_rejected(self) -> None:
        with pytest.raises(KeyError):
            _ = self._evaluate("missing-fixture")

from importlib import import_module
from typing import Protocol, cast


class _LivePublicSmokeModule(Protocol):
    def build_source_result(
        self,
        *,
        source_id: str,
        url: str,
        query: str,
        status: str,
        refresh_seconds: float,
        query_seconds: float,
        document_count: int,
        warning_count: int,
        hit_count: int,
        top_locator: str | None,
        top_locator_accepted: bool,
        error: str | None,
    ) -> dict[str, object]: ...

    def build_report(
        self, *, started_at: str, completed_at: str, sources: list[dict[str, object]]
    ) -> dict[str, object]: ...


def _module() -> _LivePublicSmokeModule:
    try:
        module = import_module("locontext.dev.live_public_smoke")
    except ModuleNotFoundError as exc:
        raise AssertionError("expected locontext.dev.live_public_smoke module") from exc
    build_source_result = getattr(module, "build_source_result", None)
    build_report = getattr(module, "build_report", None)
    if build_source_result is None or build_report is None:
        raise AssertionError(
            "expected locontext.dev.live_public_smoke.build_source_result and build_report"
        )
    return cast(_LivePublicSmokeModule, cast(object, module))


class TestLivePublicSmokeMetrics:
    def test_report_counts_track_status_totals(self) -> None:
        smoke = _module()
        report = smoke.build_report(
            started_at="2026-04-18T12:00:00Z",
            completed_at="2026-04-18T12:05:00Z",
            sources=[
                smoke.build_source_result(
                    source_id="source-1",
                    url="https://docs.example.com/guide",
                    query="guide term",
                    status="pass",
                    refresh_seconds=12.5,
                    query_seconds=0.12,
                    document_count=3,
                    warning_count=0,
                    hit_count=2,
                    top_locator="https://docs.example.com/guide/intro",
                    top_locator_accepted=True,
                    error=None,
                ),
                smoke.build_source_result(
                    source_id="source-2",
                    url="https://docs.example.com/noisy",
                    query="api token",
                    status="warn",
                    refresh_seconds=18.0,
                    query_seconds=0.09,
                    document_count=2,
                    warning_count=2,
                    hit_count=1,
                    top_locator="https://docs.example.com/noisy/api",
                    top_locator_accepted=True,
                    error="warning_budget_breached",
                ),
                smoke.build_source_result(
                    source_id="source-3",
                    url="https://code.example.com/project",
                    query="repo root",
                    status="fail",
                    refresh_seconds=61.63,
                    query_seconds=0.21,
                    document_count=0,
                    warning_count=0,
                    hit_count=0,
                    top_locator=None,
                    top_locator_accepted=False,
                    error="zero_documents",
                ),
            ],
        )
        assert report["source_count"] == 3
        assert report["pass_count"] == 1
        assert report["warn_count"] == 1
        assert report["fail_count"] == 1
        sources = cast(list[dict[str, object]], report["sources"])
        assert [source["source_id"] for source in sources] == [
            "source-1",
            "source-2",
            "source-3",
        ]

    def test_failure_semantics_cover_all_expected_classifications(self) -> None:
        smoke = _module()
        scenarios = [
            (
                "source add/refresh failure",
                smoke.build_source_result(
                    source_id="source-add-refresh",
                    url="https://docs.example.com/add-refresh",
                    query="guide term",
                    status="fail",
                    refresh_seconds=0.0,
                    query_seconds=0.0,
                    document_count=0,
                    warning_count=0,
                    hit_count=0,
                    top_locator=None,
                    top_locator_accepted=False,
                    error="source_add_refresh_failed",
                ),
            ),
            (
                "timeout",
                smoke.build_source_result(
                    source_id="source-timeout",
                    url="https://docs.example.com/timeout",
                    query="guide term",
                    status="fail",
                    refresh_seconds=30.0,
                    query_seconds=30.0,
                    document_count=0,
                    warning_count=0,
                    hit_count=0,
                    top_locator=None,
                    top_locator_accepted=False,
                    error="timeout",
                ),
            ),
            (
                "zero documents",
                smoke.build_source_result(
                    source_id="source-zero-docs",
                    url="https://docs.example.com/zero-docs",
                    query="platforms",
                    status="fail",
                    refresh_seconds=21.0,
                    query_seconds=0.15,
                    document_count=0,
                    warning_count=0,
                    hit_count=0,
                    top_locator=None,
                    top_locator_accepted=False,
                    error="zero_documents",
                ),
            ),
            (
                "zero hits",
                smoke.build_source_result(
                    source_id="source-zero-hits",
                    url="https://docs.example.com/zero-hits",
                    query="missing term",
                    status="fail",
                    refresh_seconds=14.0,
                    query_seconds=0.08,
                    document_count=2,
                    warning_count=0,
                    hit_count=0,
                    top_locator=None,
                    top_locator_accepted=False,
                    error="zero_hits",
                ),
            ),
            (
                "top locator not in accepted set",
                smoke.build_source_result(
                    source_id="source-top-locator-mismatch",
                    url="https://docs.example.com/mismatch",
                    query="guide term",
                    status="fail",
                    refresh_seconds=16.0,
                    query_seconds=0.11,
                    document_count=1,
                    warning_count=0,
                    hit_count=1,
                    top_locator="https://docs.example.com/mismatch/unexpected",
                    top_locator_accepted=False,
                    error="top_locator_not_accepted",
                ),
            ),
            (
                "warning budget breach",
                smoke.build_source_result(
                    source_id="source-warning-breach",
                    url="https://docs.example.com/warnings",
                    query="api token",
                    status="warn",
                    refresh_seconds=19.0,
                    query_seconds=0.1,
                    document_count=2,
                    warning_count=4,
                    hit_count=1,
                    top_locator="https://docs.example.com/warnings/api",
                    top_locator_accepted=True,
                    error="warning_budget_breached",
                ),
            ),
            (
                "artifact write failure",
                smoke.build_source_result(
                    source_id="source-artifact-write",
                    url="https://docs.example.com/artifacts",
                    query="artifact path",
                    status="fail",
                    refresh_seconds=10.0,
                    query_seconds=0.07,
                    document_count=1,
                    warning_count=0,
                    hit_count=1,
                    top_locator="https://docs.example.com/artifacts/overview",
                    top_locator_accepted=True,
                    error="artifact_write_failed",
                ),
            ),
        ]
        expected = {
            "source add/refresh failure": ("fail", "source_add_refresh_failed"),
            "timeout": ("fail", "timeout"),
            "zero documents": ("fail", "zero_documents"),
            "zero hits": ("fail", "zero_hits"),
            "top locator not in accepted set": ("fail", "top_locator_not_accepted"),
            "warning budget breach": ("warn", "warning_budget_breached"),
            "artifact write failure": ("fail", "artifact_write_failed"),
        }
        for scenario_name, source in scenarios:
            expected_status, expected_error = expected[scenario_name]
            assert source["status"] == expected_status
            assert source["error"] == expected_error
            assert source["status"] in {"pass", "warn", "fail"}

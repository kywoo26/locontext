from importlib import import_module
from typing import Protocol, cast

EXPECTED_REPORT_FIELDS = {
    "started_at",
    "completed_at",
    "source_count",
    "pass_count",
    "warn_count",
    "fail_count",
    "sources",
}
EXPECTED_SOURCE_FIELDS = {
    "source_id",
    "url",
    "query",
    "status",
    "refresh_seconds",
    "query_seconds",
    "document_count",
    "warning_count",
    "hit_count",
    "top_locator",
    "top_locator_accepted",
    "error",
}
EXPECTED_STATUSES = {"pass", "warn", "fail"}


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


class TestLivePublicSmokeContract:
    def _assert_failure_case(
        self,
        *,
        status: str,
        error: str,
        document_count: int,
        hit_count: int,
        warning_count: int,
        top_locator: str | None,
        top_locator_accepted: bool,
    ) -> None:
        smoke = _module()
        source = smoke.build_source_result(
            source_id="source-failure-case",
            url="https://docs.example.com/failure",
            query="failure query",
            status=status,
            refresh_seconds=0.0,
            query_seconds=0.0,
            document_count=document_count,
            warning_count=warning_count,
            hit_count=hit_count,
            top_locator=top_locator,
            top_locator_accepted=top_locator_accepted,
            error=error,
        )
        assert source["status"] == status
        assert source["error"] == error
        assert source["document_count"] == document_count
        assert source["hit_count"] == hit_count
        assert source["warning_count"] == warning_count
        assert source["top_locator"] == top_locator
        assert source["top_locator_accepted"] == top_locator_accepted

    def test_report_uses_exact_top_level_schema(self) -> None:
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
            ],
        )
        assert set(report) == EXPECTED_REPORT_FIELDS
        assert report["started_at"] == "2026-04-18T12:00:00Z"
        assert report["completed_at"] == "2026-04-18T12:05:00Z"
        assert report["source_count"] == 2
        assert report["pass_count"] == 1
        assert report["warn_count"] == 1
        assert report["fail_count"] == 0
        assert len(cast(list[dict[str, object]], report["sources"])) == 2

    def test_source_entries_use_exact_per_source_schema(self) -> None:
        smoke = _module()
        source = smoke.build_source_result(
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
        )
        assert set(source) == EXPECTED_SOURCE_FIELDS
        assert source["status"] in EXPECTED_STATUSES
        assert source["source_id"] == "source-3"
        assert source["url"] == "https://code.example.com/project"
        assert source["query"] == "repo root"
        assert source["error"] == "zero_documents"

    def test_status_vocabulary_is_fixed_to_pass_warn_fail(self) -> None:
        assert EXPECTED_STATUSES == {"pass", "warn", "fail"}
        assert sorted(EXPECTED_STATUSES) == ["fail", "pass", "warn"]

    def test_timeout_is_classified_as_fail(self) -> None:
        self._assert_failure_case(
            status="fail",
            error="timeout",
            document_count=0,
            hit_count=0,
            warning_count=0,
            top_locator=None,
            top_locator_accepted=False,
        )

    def test_zero_documents_and_zero_hits_are_classified_as_fail(self) -> None:
        self._assert_failure_case(
            status="fail",
            error="zero_documents",
            document_count=0,
            hit_count=0,
            warning_count=0,
            top_locator=None,
            top_locator_accepted=False,
        )

    def test_warning_budget_breach_is_classified_as_warn(self) -> None:
        self._assert_failure_case(
            status="warn",
            error="warning_budget_breached",
            document_count=2,
            hit_count=1,
            warning_count=4,
            top_locator="https://docs.example.com/failure/warn",
            top_locator_accepted=True,
        )

    def test_artifact_write_failure_is_classified_as_fail(self) -> None:
        self._assert_failure_case(
            status="fail",
            error="artifact_write_failed",
            document_count=1,
            hit_count=1,
            warning_count=0,
            top_locator="https://docs.example.com/failure/artifact",
            top_locator_accepted=True,
        )

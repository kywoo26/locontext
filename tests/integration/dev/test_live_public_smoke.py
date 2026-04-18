from collections.abc import Callable
from importlib import import_module
from inspect import Parameter, signature
from pathlib import Path
from typing import cast

import pytest

pytestmark = pytest.mark.integration

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


def _execution_entrypoint(module: object) -> Callable[..., object]:
    for name in ("main", "run"):
        entrypoint = cast(Callable[..., object] | None, getattr(module, name, None))
        if callable(entrypoint):
            return entrypoint

    raise AssertionError(
        "expected a runnable entrypoint such as locontext.dev.live_public_smoke.main()"
    )


def _invoke_entrypoint(entrypoint: Callable[..., object], output_dir: Path) -> object:
    params = list(signature(entrypoint).parameters.values())
    if not params:
        return entrypoint()

    first = params[0]
    if first.kind in {Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD}:
        return entrypoint(output_dir)
    if first.kind is Parameter.KEYWORD_ONLY:
        return entrypoint(output_dir=output_dir)

    raise AssertionError("unsupported execution entrypoint signature")


def test_live_public_smoke_wrapper_uses_structured_artifacts(tmp_path: Path) -> None:
    module = cast(object, import_module("locontext.dev.live_public_smoke"))
    entrypoint = _execution_entrypoint(module)

    result = cast(dict[str, object], _invoke_entrypoint(entrypoint, tmp_path))

    report_path = cast(Path | None, result.get("report_path"))
    run_log_path = cast(Path | None, result.get("run_log_path"))
    if report_path is None or run_log_path is None:
        raise AssertionError(
            "expected execution result to include report_path and run_log_path"
        )

    assert report_path.exists()
    assert run_log_path.exists()

    report = cast(dict[str, object] | None, result.get("report"))
    if report is None:
        raise AssertionError("expected execution result to include a structured report")

    assert set(report) == EXPECTED_REPORT_FIELDS
    source_count = cast(int, report["source_count"])
    pass_count = cast(int, report["pass_count"])
    warn_count = cast(int, report["warn_count"])
    fail_count = cast(int, report["fail_count"])
    assert source_count >= 1
    assert pass_count + warn_count + fail_count == source_count

    sources = cast(list[dict[str, object]], report["sources"])
    assert len(sources) == source_count
    assert all(set(source) == EXPECTED_SOURCE_FIELDS for source in sources)
    assert {source["status"] for source in sources} <= EXPECTED_STATUSES

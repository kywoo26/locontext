from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, cast
from uuid import uuid4

from ..sources.web.canonicalize import canonicalize_locator

STATUS_PASS: Final[str] = "pass"
STATUS_WARN: Final[str] = "warn"
STATUS_FAIL: Final[str] = "fail"
STATUS_VOCABULARY: Final[tuple[str, str, str]] = (
    STATUS_PASS,
    STATUS_WARN,
    STATUS_FAIL,
)


@dataclass(slots=True, frozen=True)
class CuratedPublicSource:
    source_id: str
    url: str
    query: str
    accepted_top_locators: tuple[str, ...]
    warning_budget: int | None = None


@dataclass(slots=True, frozen=True)
class RunArtifacts:
    output_dir: Path
    report_path: Path
    run_log_path: Path


CURATED_PUBLIC_SOURCES: Final[tuple[CuratedPublicSource, ...]] = (
    CuratedPublicSource(
        source_id="source-1",
        url="https://docs.python.org/3/tutorial/",
        query="control flow",
        accepted_top_locators=("https://docs.python.org/3/tutorial/controlflow.html",),
        warning_budget=2,
    ),
    CuratedPublicSource(
        source_id="source-2",
        url="https://docs.docker.com/",
        query="docker compose",
        accepted_top_locators=("https://docs.docker.com/compose/",),
        warning_budget=2,
    ),
    CuratedPublicSource(
        source_id="source-3",
        url="https://go.dev/doc/tutorial/",
        query="getting started",
        accepted_top_locators=(
            "https://go.dev/doc/tutorial/getting-started",
            "https://go.dev/doc/tutorial/fuzz",
        ),
        warning_budget=2,
    ),
    CuratedPublicSource(
        source_id="source-4",
        url="https://doc.rust-lang.org/book/",
        query="ownership",
        accepted_top_locators=(
            "https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html",
            "https://doc.rust-lang.org/stable/book/print.html",
        ),
        warning_budget=2,
    ),
    CuratedPublicSource(
        source_id="source-5",
        url="https://react.dev/learn",
        query="hooks",
        accepted_top_locators=("https://react.dev/learn",),
        warning_budget=2,
    ),
    CuratedPublicSource(
        source_id="source-6",
        url="https://tailwindcss.com/docs/installation",
        query="utility classes",
        accepted_top_locators=(
            "https://tailwindcss.com/docs/installation/framework-guides",
        ),
        warning_budget=2,
    ),
    CuratedPublicSource(
        source_id="source-7",
        url="https://www.sqlite.org/about.html",
        query="sql",
        accepted_top_locators=("https://www.sqlite.org/lang.html",),
        warning_budget=2,
    ),
    CuratedPublicSource(
        source_id="source-8",
        url="https://developer.mozilla.org/en-US/docs/Learn",
        query="html",
        accepted_top_locators=(
            "https://developer.mozilla.org/en-US/docs/MDN/Tutorials",
        ),
        warning_budget=2,
    ),
    CuratedPublicSource(
        source_id="source-9",
        url="https://docs.github.com/en/actions",
        query="workflow syntax",
        accepted_top_locators=(
            "https://docs.github.com/en/actions/how-tos/troubleshoot-workflows",
            "https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions",
        ),
        warning_budget=2,
    ),
    CuratedPublicSource(
        source_id="source-10",
        url="https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html",
        query="iam policy",
        accepted_top_locators=(
            "https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot.html",
            "https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html",
        ),
        warning_budget=2,
    ),
)


def build_source_result(
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
) -> dict[str, object]:
    _validate_status(status)
    return {
        "source_id": source_id,
        "url": url,
        "query": query,
        "status": status,
        "refresh_seconds": refresh_seconds,
        "query_seconds": query_seconds,
        "document_count": document_count,
        "warning_count": warning_count,
        "hit_count": hit_count,
        "top_locator": top_locator,
        "top_locator_accepted": top_locator_accepted,
        "error": error,
    }


def build_report(
    *,
    started_at: str,
    completed_at: str,
    sources: list[dict[str, object]],
) -> dict[str, object]:
    pass_count = 0
    warn_count = 0
    fail_count = 0
    normalized_sources: list[dict[str, object]] = []

    for source in sources:
        status = str(source["status"])
        _validate_status(status)
        if status == STATUS_PASS:
            pass_count += 1
        elif status == STATUS_WARN:
            warn_count += 1
        else:
            fail_count += 1
        normalized_sources.append(dict(source))

    return {
        "started_at": started_at,
        "completed_at": completed_at,
        "source_count": len(normalized_sources),
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "sources": normalized_sources,
    }


def prepare_run_artifacts(
    output_dir: Path | str, *, run_id: str | None = None
) -> RunArtifacts:
    base_dir = Path(output_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    run_dir = base_dir / _run_dir_name(run_id)
    run_dir.mkdir(parents=True, exist_ok=False)
    return RunArtifacts(
        output_dir=run_dir,
        report_path=run_dir / "report.json",
        run_log_path=run_dir / "run.log",
    )


def default_run_artifacts(output_root: Path | str) -> RunArtifacts:
    return prepare_run_artifacts(output_root)


def _run_dir_name(run_id: str | None) -> str:
    if run_id is not None and run_id.strip():
        return run_id.strip()
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{timestamp}-{uuid4().hex[:8]}"


def _validate_status(status: str) -> None:
    if status not in STATUS_VOCABULARY:
        msg = f"invalid smoke status: {status!r}"
        raise ValueError(msg)


def _run_cli(
    args: list[str], cwd: Path, timeout: float = 300.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "locontext.cli.main", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _is_accepted_locator(locator: str, accepted_set: tuple[str, ...]) -> bool:
    try:
        canonical_locator = canonicalize_locator(locator).canonical_locator
        canonical_accepted = {
            canonicalize_locator(a).canonical_locator for a in accepted_set
        }
        return canonical_locator in canonical_accepted
    except Exception:
        return locator in accepted_set


def main(output_dir: Path | str | None = None) -> dict[str, object]:
    if output_dir is None:
        parser = argparse.ArgumentParser(
            description="Run live public source smoke test."
        )
        _ = parser.add_argument(
            "--output-dir", type=Path, help="Directory for run artifacts"
        )
        args = parser.parse_args()
        output_root = cast(Path | None, args.output_dir) or Path(
            "artifacts/live-public-smoke"
        )
    else:
        output_root = Path(output_dir)

    artifacts = default_run_artifacts(output_root)
    started_at = datetime.now(tz=UTC).isoformat()

    source_results: list[dict[str, object]] = []

    with artifacts.run_log_path.open("w", encoding="utf-8") as log:
        _ = log.write(f"Starting live public smoke run at {started_at}\n")
        _ = log.write(f"Output directory: {artifacts.output_dir}\n")

        with tempfile.TemporaryDirectory(prefix="locontext-smoke-") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            _ = log.write(f"Using isolated temp directory: {temp_dir}\n")

            _ = log.write("Running locontext init...\n")
            res = _run_cli(["init"], temp_dir)
            if res.returncode != 0:
                _ = log.write(f"init failed: {res.stderr}\n")
                completed_at = datetime.now(tz=UTC).isoformat()
                report = build_report(
                    started_at=started_at, completed_at=completed_at, sources=[]
                )
                _ = artifacts.report_path.write_text(
                    json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
                )
                return {
                    "output_dir": artifacts.output_dir,
                    "report_path": artifacts.report_path,
                    "run_log_path": artifacts.run_log_path,
                    "report": report,
                }

            for source in CURATED_PUBLIC_SOURCES:
                _ = log.write(f"Processing source: {source.source_id} ({source.url})\n")
                error: str | None = None
                status = STATUS_PASS
                refresh_seconds = 0.0
                query_seconds = 0.0
                document_count = 0
                warning_count = 0
                hit_count = 0
                top_locator: str | None = None
                top_locator_accepted = False

                try:
                    res = _run_cli(["source", "add", source.url], temp_dir)
                    if res.returncode != 0:
                        status = STATUS_FAIL
                        error = "source_add_refresh_failed"
                        _ = log.write(f"source add failed: {res.stderr}\n")
                    else:
                        match = re.search(r"source: ([a-f0-9]+)", res.stdout)
                        internal_id = match.group(1) if match else None
                        if not internal_id:
                            status = STATUS_FAIL
                            error = "source_add_refresh_failed"
                            _ = log.write(
                                "failed to extract source_id from add output\n"
                            )
                        else:
                            start_refresh = time.perf_counter()
                            res = _run_cli(["source", "refresh", internal_id], temp_dir)
                            refresh_seconds = time.perf_counter() - start_refresh

                            if res.returncode != 0:
                                status = STATUS_FAIL
                                error = "source_add_refresh_failed"
                                _ = log.write(f"source refresh failed: {res.stderr}\n")
                            else:
                                doc_match = re.search(r"documents: (\d+)", res.stdout)
                                document_count = (
                                    int(doc_match.group(1)) if doc_match else 0
                                )
                                warn_match = re.search(r"warnings: (\d+)", res.stdout)
                                warning_count = (
                                    int(warn_match.group(1)) if warn_match else 0
                                )

                                if document_count == 0:
                                    status = STATUS_FAIL
                                    error = "zero_documents"
                                elif (
                                    source.warning_budget is not None
                                    and warning_count > source.warning_budget
                                ):
                                    status = STATUS_WARN
                                    error = "warning_budget_breached"

                                if error != "zero_documents":
                                    start_query = time.perf_counter()
                                    res = _run_cli(
                                        ["query", source.query, "--json"], temp_dir
                                    )
                                    query_seconds = time.perf_counter() - start_query

                                    if res.returncode != 0:
                                        status = STATUS_FAIL
                                        error = "query_failed"
                                        _ = log.write(f"query failed: {res.stderr}\n")
                                    else:
                                        try:
                                            query_data = cast(
                                                dict[str, object],
                                                json.loads(res.stdout),
                                            )
                                            hit_count = cast(
                                                int, query_data.get("hit_count", 0)
                                            )
                                            hits = cast(
                                                list[dict[str, object]],
                                                query_data.get("hits", []),
                                            )
                                            if hit_count > 0 and hits:
                                                top_locator = cast(
                                                    str | None,
                                                    hits[0].get("document_locator"),
                                                )
                                                top_locator_accepted = (
                                                    _is_accepted_locator(
                                                        top_locator or "",
                                                        source.accepted_top_locators,
                                                    )
                                                )

                                            if hit_count == 0:
                                                status = STATUS_FAIL
                                                error = "zero_hits"
                                            elif not top_locator_accepted:
                                                status = STATUS_FAIL
                                                error = "top_locator_not_accepted"
                                        except json.JSONDecodeError:
                                            status = STATUS_FAIL
                                            error = "query_failed"
                                            _ = log.write(
                                                "failed to parse query JSON output\n"
                                            )
                except subprocess.TimeoutExpired:
                    status = STATUS_FAIL
                    error = "timeout"
                    _ = log.write(f"source {source.source_id} timed out\n")
                except Exception as exc:
                    status = STATUS_FAIL
                    error = "internal_error"
                    _ = log.write(f"source {source.source_id} failed: {exc}\n")

                source_result = build_source_result(
                    source_id=source.source_id,
                    url=source.url,
                    query=source.query,
                    status=status,
                    refresh_seconds=refresh_seconds,
                    query_seconds=query_seconds,
                    document_count=document_count,
                    warning_count=warning_count,
                    hit_count=hit_count,
                    top_locator=top_locator,
                    top_locator_accepted=top_locator_accepted,
                    error=error,
                )

                try:
                    evidence_path = (
                        artifacts.output_dir / f"source-{source.source_id}.json"
                    )
                    _ = evidence_path.write_text(
                        json.dumps(source_result, indent=2, sort_keys=True),
                        encoding="utf-8",
                    )
                except Exception as exc:
                    _ = log.write(
                        f"failed to write evidence for {source.source_id}: {exc}\n"
                    )
                    source_result = {
                        **source_result,
                        "status": STATUS_FAIL,
                        "error": "artifact_write_failed",
                    }

                source_results.append(source_result)

    completed_at = datetime.now(tz=UTC).isoformat()
    report = build_report(
        started_at=started_at,
        completed_at=completed_at,
        sources=source_results,
    )

    _ = artifacts.report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )

    return {
        "output_dir": artifacts.output_dir,
        "report_path": artifacts.report_path,
        "run_log_path": artifacts.run_log_path,
        "report": report,
    }


def run(output_dir: Path | str | None = None) -> dict[str, object]:
    return main(output_dir=output_dir)


if __name__ == "__main__":
    _ = main()
